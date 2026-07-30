# verify_cuda.py
import torch

print(f"PyTorch版本: {torch.__version__}")
print(f"CUDA可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA设备数量: {torch.cuda.device_count()}")
    print(f"当前设备: {torch.cuda.current_device()}")
    print(f"设备名称: {torch.cuda.get_device_name(0)}")
    print(
        f"设备内存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB"
    )
else:
    print("未检测到CUDA设备，请检查GPU驱动和PyTorch安装")
