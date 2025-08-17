# GPU 환경 설치 가이드

## 표준 PyPI 패키지
```bash
pip install -r requirements.txt
```

## GPU 가속 패키지 (선택사항)
**⚠️ NVIDIA GPU + CUDA 13.0 환경에서만 필요**

### PaddlePaddle GPU 버전 설치
```bash
# 공식 PaddlePaddle 저장소에서 설치 (PyPI에서 지원하지 않음)
pip install paddlepaddle-gpu==3.1.0 -i https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn

# 또는 공식 저장소
pip install paddlepaddle-gpu==3.1.0 -f https://www.paddlepaddle.org.cn/whl/windows/mkl/avx/stable.html
```

### PaddleOCR 설치
```bash
pip install paddleocr==3.1.1
```

## CPU 전용 환경 (GPU 없는 경우)
```bash
# 표준 PyPI 패키지만 설치
pip install -r requirements.txt
pip install paddlepaddle==3.1.0  # CPU 버전
pip install paddleocr==3.1.1
```

## 환경 검증
```python
import paddle
print(f"GPU 지원: {paddle.is_compiled_with_cuda()}")
print(f"GPU 개수: {paddle.device.cuda.device_count() if paddle.is_compiled_with_cuda() else 0}")
```

## 이식성 고려사항
1. **requirements.txt**: 표준 PyPI 패키지만 포함
2. **requirements-gpu.txt**: GPU 전용 패키지 별도 관리
3. **환경별 설치 스크립트**: setup_cpu.sh, setup_gpu.sh 제공
4. **Docker**: GPU/CPU 환경별 컨테이너 이미지 제공
