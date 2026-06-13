# move_controller.py (가상 테스트용 Mock 모듈)
import time

def navigate_to(coordinate_string):
    """
    ROS 2 환경 없이 PC 1 -> PC 2 웹소켓 통신 및 LLM 파이프라인이 
    제어 모듈의 끝단까지 잘 연결되는지 확인하기 위한 더미 함수입니다.
    """
    print(f"       [가상 환경 테스트] 🚀 모터 제어 신호 수신됨! 목표 좌표: {coordinate_string}")
    
    # 실제 로봇이 이동하는 것처럼 3초간 대기 (통신 끊김 방지 로직 테스트 겸용)
    for i in range(1, 4):
        print(f"       ... 가상 이동 중 ({i}초) ...")
        time.sleep(1)
        
    print(f"       [가상 환경 테스트] ✅ 목표 좌표 도착 완료 보고!")
    
    # 항상 성공(True)을 반환하여 다음 시퀀스로 넘어가도록 유도
    return True