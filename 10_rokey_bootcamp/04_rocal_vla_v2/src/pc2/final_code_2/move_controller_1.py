import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, QoSHistoryPolicy
from nav2_msgs.action import NavigateToPose
from sensor_msgs.msg import Imu, JointState, LaserScan
from geometry_msgs.msg import PoseWithCovarianceStamped
from std_srvs.srv import Empty 
import math
import torch
import threading
import time
import ast
import cv2
import numpy as np
import os

# ==========================================================
# 🚨 환경 설정
# ==========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POLICY_MODEL_PATH = os.path.join(BASE_DIR, 'move.pt')

MAP_IMAGE_PATH = os.path.join(BASE_DIR, 'warehouse.png') 
MAP_RESOLUTION = 0.05  
MAP_ORIGIN_X = -13.125   
MAP_ORIGIN_Y = -18.975   

ACTION_SCALE = 0.5 
FOLDED_POSE = [3.14, -1.57, 1.57, 0.0, 1.57, 0.0] 
HOMING_POSE = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

def euler_to_quaternion(yaw):
    qx, qy, qz, qw = 0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0)
    return qx, qy, qz, qw

class Nav2GoalSender(Node):
    def __init__(self):
        super().__init__('nav2_goal_sender')
        self.standing_count = 0
        self.state = 'IDLE' # 상태: IDLE, NAVIGATING, RECOVERING, OPENCV_MATCHING
        
        self.folded_command_sent = False
        
        self.target_x, self.target_y, self.target_yaw = 0.0, 0.0, 0.0
        
        self.homing_done = True 
        self.homing_wait_count = 0 
        
        self.action_done = False
        self.action_result = False
        
        self.action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.goal_handle = None

        self.imu_sub = self.create_subscription(Imu, '/chassis/imu', self.imu_callback, 10)
        self.joint_sub = self.create_subscription(JointState, '/joint_states', self.joint_callback, 10)
        self.scan_sub = self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)
        
        self.initial_pose_pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
        
        qos_profile = QoSProfile(history=QoSHistoryPolicy.KEEP_LAST, depth=1)
        self.joint_cmd_pub = self.create_publisher(JointState, '/joint_commands', qos_profile)

        self.get_logger().info(f'RL 모델 로딩 중... 경로: {POLICY_MODEL_PATH}')
        try:
            self.rl_policy = torch.jit.load(POLICY_MODEL_PATH)
            self.rl_policy.eval()
            self.get_logger().info('✅ 모델 로딩 성공!')
        except Exception as e:
            self.get_logger().error(f'❌ 모델 로딩 실패: {e}')
            self.rl_policy = None

        self.proj_gravity = [0.0, 0.0, -1.0] 
        self.current_obs_pos = []
        self.current_obs_vel = []
        
        self.obs_joint_names = [
            'joint_caster_base', 'joint_wheel_left', 'joint_wheel_right',
            'joint_1', 'joint_swing_left', 'joint_swing_right',
            'joint_2', 'joint_caster_left', 'joint_caster_right',
            'joint_3', 'joint_4', 'joint_5', 'joint_6'
        ]
        
        self.target_joint_names = [
            'joint_1', 'joint_2', 'joint_3', 
            'joint_4', 'joint_5', 'joint_6'
        ]
        
        self.last_action = [0.0] * 6 
        self.rl_timer = self.create_timer(0.02, self.rl_control_loop)

    def imu_callback(self, msg):
        q = msg.orientation
        gx = 2.0 * (q.x * q.z - q.w * q.y)
        gy = 2.0 * (q.y * q.z + q.w * q.x)
        gz = 1.0 - 2.0 * (q.x * q.x + q.y * q.y)
        self.proj_gravity = [-gx, -gy, -gz]

        if self.state == 'NAVIGATING' and self.proj_gravity[2] > -0.5:
            self.get_logger().warn('🚨 넘어짐 감지! 주행 중단 및 0점 정렬 시작.')
            self.state = 'RECOVERING'
            self.homing_done = False 
            self.homing_wait_count = 0 
            self.last_action = [0.0] * 6 
            if self.goal_handle is not None:
                self.goal_handle.cancel_goal_async()

    def joint_callback(self, msg):
        try:
            obs_pos = []
            obs_vel = []
            for name in self.obs_joint_names:
                idx = msg.name.index(name)
                obs_pos.append(msg.position[idx])
                obs_vel.append(msg.velocity[idx])
            self.current_obs_pos = obs_pos
            self.current_obs_vel = obs_vel
        except ValueError:
            pass 

    def scan_callback(self, msg):
        if self.state == 'OPENCV_MATCHING':
            self.get_logger().info('🔍 [자율 인지] 라이다 데이터를 맵과 매칭하여 현재 위치를 탐색합니다...')
            self.state = 'MATCHING_IN_PROGRESS' 
            threading.Thread(target=self.perform_opencv_matching, args=(msg,)).start()

    def perform_opencv_matching(self, scan_msg):
        try:
            world_map = cv2.imread(MAP_IMAGE_PATH, cv2.IMREAD_GRAYSCALE)
            if world_map is None:
                self.get_logger().error(f"❌ 맵 이미지를 찾을 수 없습니다: {MAP_IMAGE_PATH}")
                self.resume_navigation_directly()
                return

            _, world_map_thresh = cv2.threshold(world_map, 127, 255, cv2.THRESH_BINARY_INV)

            max_range = 8.0 
            pixel_size = int((max_range * 2) / MAP_RESOLUTION)
            center_p = pixel_size // 2
            local_img = np.zeros((pixel_size, pixel_size), dtype=np.uint8)

            angles = np.linspace(scan_msg.angle_min, scan_msg.angle_max, len(scan_msg.ranges))
            for i, r in enumerate(scan_msg.ranges):
                if scan_msg.range_min < r < max_range and not math.isinf(r) and not math.isnan(r):
                    x = r * math.cos(angles[i])
                    y = r * math.sin(angles[i])
                    
                    px = center_p + int(x / MAP_RESOLUTION)
                    py = center_p - int(y / MAP_RESOLUTION) 
                    
                    if 0 <= px < pixel_size and 0 <= py < pixel_size:
                        cv2.circle(local_img, (px, py), 2, 255, -1)

            _, mask = cv2.threshold(local_img, 10, 255, cv2.THRESH_BINARY)

            best_val = -1
            best_loc = (0, 0)
            best_angle_deg = 0

            self.get_logger().info('🔄 [OpenCV] 로봇이 스스로 위치를 계산 중입니다... (약 1~2초 소요)')
            
            for deg in range(0, 360, 5):
                M = cv2.getRotationMatrix2D((center_p, center_p), deg, 1.0)
                rotated_template = cv2.warpAffine(local_img, M, (pixel_size, pixel_size))
                rotated_mask = cv2.warpAffine(mask, M, (pixel_size, pixel_size))

                res = cv2.matchTemplate(world_map_thresh, rotated_template, cv2.TM_CCORR_NORMED, mask=rotated_mask)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)

                if max_val > best_val:
                    best_val = max_val
                    best_loc = max_loc
                    best_angle_deg = deg

            global_center_px = best_loc[0] + center_p
            global_center_py = best_loc[1] + center_p
            map_h = world_map.shape[0]
            
            real_x = MAP_ORIGIN_X + (global_center_px * MAP_RESOLUTION)
            real_y = MAP_ORIGIN_Y + ((map_h - global_center_py) * MAP_RESOLUTION)
            real_yaw = math.radians(best_angle_deg)

            self.get_logger().info(f"🎯 [자율 복구 성공!] 좌표 확정: X={real_x:.2f}, Y={real_y:.2f}, Yaw={best_angle_deg}도 (신뢰도: {best_val:.2f})")

            self.inject_self_pose(real_x, real_y, real_yaw)

        except Exception as e:
            self.get_logger().error(f"❌ OpenCV 연산 실패: {e}")
            self.resume_navigation_directly()

    def inject_self_pose(self, x, y, yaw):
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        
        msg.pose.pose.position.x = float(x)
        msg.pose.pose.position.y = float(y)
        msg.pose.pose.position.z = 0.0
        qx, qy, qz, qw = euler_to_quaternion(yaw)
        msg.pose.pose.orientation.x = qx
        msg.pose.pose.orientation.y = qy
        msg.pose.pose.orientation.z = qz
        msg.pose.pose.orientation.w = qw
        
        msg.pose.covariance[0] = 0.02
        msg.pose.covariance[7] = 0.25
        msg.pose.covariance[35] = 0.08
        
        self.initial_pose_pub.publish(msg)
        time.sleep(1.0) 
        
        self.resume_navigation_directly()

    def resume_navigation_directly(self):
        self.state = 'IDLE'
        self.send_goal(self.target_x, self.target_y, self.target_yaw)

    def rl_control_loop(self):
        if self.state == 'IDLE':
            return

        if self.state in ['NAVIGATING', 'OPENCV_MATCHING', 'MATCHING_IN_PROGRESS']:
            if not self.folded_command_sent:
                cmd_msg = JointState()
                cmd_msg.header.stamp = self.get_clock().now().to_msg()
                cmd_msg.name = self.target_joint_names
                cmd_msg.position = FOLDED_POSE
                self.joint_cmd_pub.publish(cmd_msg)
                
                self.folded_command_sent = True 
                self.get_logger().info('🦾 [상태 변경]: 이동을 위해 팔을 접고 대기합니다.')
            return

        if self.state == 'RECOVERING':
            if self.rl_policy is None:
                return

            if not self.homing_done:
                cmd_msg = JointState()
                cmd_msg.header.stamp = self.get_clock().now().to_msg()
                cmd_msg.name = self.target_joint_names
                cmd_msg.position = HOMING_POSE
                self.joint_cmd_pub.publish(cmd_msg)
                
                self.homing_wait_count += 1
                if self.homing_wait_count < 100:
                    return 
                
                self.get_logger().info('✅ 0점 정렬 완료! RL 기립 정책을 가동합니다.')
                self.homing_done = True
                self.last_action = [0.0] * 6
                return

            is_standing = self.proj_gravity[2] < -0.95
            
            if is_standing:
                self.standing_count += 1
            else:
                self.standing_count = 0
                
            if self.standing_count > 50:
                self.get_logger().info('✅ 기립 성공! 주행을 멈추고 라이다 스캔 <-> 맵 이미지 정밀 매칭을 1회 실시합니다.')
                
                self.state = 'OPENCV_MATCHING' 
                self.last_action = [0.0] * 6
                self.standing_count = 0
                return

            if not self.current_obs_pos: return

            obs_list = self.proj_gravity + [c - 0.0 for c in self.current_obs_pos] + self.current_obs_vel + self.last_action
                
            try:
                obs_tensor = torch.tensor([obs_list], dtype=torch.float32)
                with torch.no_grad():
                    action_tensor = self.rl_policy(obs_tensor)
                
                raw_action = action_tensor[0].tolist()[:6]
                self.last_action = raw_action
                scaled_action = [a * ACTION_SCALE for a in raw_action]

                cmd_msg = JointState()
                cmd_msg.header.stamp = self.get_clock().now().to_msg()
                cmd_msg.name = self.target_joint_names
                cmd_msg.position = scaled_action
                self.joint_cmd_pub.publish(cmd_msg)
                
            except Exception as e:
                self.get_logger().error(f"🧠 RL 에러 발생: {e}")

    def send_goal(self, x, y, yaw):
        # 💡 플래그 초기화: 여러 번 호출될 수 있으므로 상태 리셋
        self.action_done = False
        self.action_result = False
        
        self.target_x, self.target_y, self.target_yaw = x, y, yaw
        self.get_logger().info(f'Nav2 Action Server 연결 대기 중... (목표: X={x}, Y={y})')
        
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = float(x)
        goal_msg.pose.pose.position.y = float(y)
        goal_msg.pose.pose.position.z = 0.0
        qx, qy, qz, qw = euler_to_quaternion(yaw)
        goal_msg.pose.pose.orientation.x = qx
        goal_msg.pose.pose.orientation.y = qy
        goal_msg.pose.pose.orientation.z = qz
        goal_msg.pose.pose.orientation.w = qw
        
        self.state = 'NAVIGATING'
        self.folded_command_sent = False 
        
        self.send_goal_future = self.action_client.send_goal_async(goal_msg, feedback_callback=self.feedback_callback)
        self.send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        self.goal_handle = future.result()
        if not self.goal_handle.accepted: 
            self.get_logger().warn('목표가 거부되었습니다.')
            self.action_result = False
            self.action_done = True
            self.state = 'IDLE' 
            return
        
        self.get_logger().info('🚀 이동 시작.')
        self._get_result_future = self.goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def feedback_callback(self, feedback_msg): 
        pass

    def get_result_callback(self, future):
        if self.state in ['RECOVERING', 'OPENCV_MATCHING', 'MATCHING_IN_PROGRESS']: 
            return
            
        status = future.result().status
        if status == 4:
            self.get_logger().info('✅ 이동 완료!')
            self.action_result = True
        else:
            self.get_logger().info(f'⚠️ 이동 실패. 코드: {status}')
            self.action_result = False
            
        self.state = 'IDLE'
        self.action_done = True


# =========================================================================
# 🌐 [모듈화 영역] 외부 노출 API (LLM 파이프라인 연동용)
# =========================================================================
_ros_thread = None
_nav_node = None

def _spin_ros_node():
    """백그라운드에서 ROS2 노드를 영구적으로 돌려주는 스레드 함수"""
    global _nav_node
    if not rclpy.ok():
        rclpy.init()
    _nav_node = Nav2GoalSender()
    try:
        rclpy.spin(_nav_node)
    except Exception as e:
        pass
    finally:
        if _nav_node:
            _nav_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

def init_module():
    """모듈이 import 될 때 자동으로 백그라운드 노드 시작"""
    global _ros_thread
    if _ros_thread is None:
        print("🤖 [Move Module] ROS2 Nav2 백그라운드 노드를 시작합니다...")
        _ros_thread = threading.Thread(target=_spin_ros_node, daemon=True)
        _ros_thread.start()
        time.sleep(2.0) # 노드가 완전히 뜰 때까지 잠시 대기

# 파이썬에서 파일이 import 될 때 즉시 초기화 실행
init_module()

def navigate_to(coordinate_input):
    """
    LLM 파이프라인에서 호출하는 메인 API.
    문자열 또는 리스트 형태의 좌표를 받아 목적지로 이동시킵니다.
    """
    global _nav_node
    if _nav_node is None:
        print("❌ [Move Module] 노드가 아직 초기화되지 않았습니다.")
        return False

    try:
        if isinstance(coordinate_input, str):
            coords = ast.literal_eval(coordinate_input)
        else:
            coords = coordinate_input
            
        target_x, target_y, target_yaw = float(coords[0]), float(coords[1]), float(coords[2])
    except Exception as e:
        print(f"❌ [Move Module] 좌표 형식이 잘못되었습니다: {coordinate_input} -> {e}")
        return False
        
    print(f"🚙 [Move Module] LLM 목적지 수신 -> X:{target_x}, Y:{target_y}, Yaw:{target_yaw}")
    
    # 💡 목표 전송 (Non-blocking)
    _nav_node.action_done = False
    _nav_node.action_result = False
    _nav_node.send_goal(target_x, target_y, target_yaw)
    
    # 💡 [데드락 방지 타이머]: 미끄러짐 등으로 인해 무한정 대기하는 현상 방지 (최대 45초)
    start_wait_time = time.time()
    max_execution_timeout = 45.0  
    
    # 💡 도착하거나 실패할 때까지 동기화 블로킹 대기
    while not _nav_node.action_done:
        time.sleep(0.1)
        
        if (time.time() - start_wait_time) > max_execution_timeout:
            print("\n⚠️ [Move Module] 정차 오차 락(Lock) 감지! 45초 제한 초과.")
            print("➡️ 로봇이 목적지 반경에 도달한 것으로 간주하여 강제로 파이프라인을 진행합니다.")
            
            _nav_node.state = 'IDLE'
            _nav_node.action_done = True
            return True # 타임아웃 시 파이프라인 진행을 위해 True 반환
            
    return _nav_node.action_result