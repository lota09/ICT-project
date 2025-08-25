import logging
import os

def setup_logger():
    """
    중앙집중식 로거 설정
    모든 모듈에서 동일한 로거를 사용하도록 함
    """
    logger = logging.getLogger("notification_crawler")
    
    if not logger.handlers:
        handler = logging.FileHandler('app.log', encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.info("Centralized logger initialized")
    
    return logger