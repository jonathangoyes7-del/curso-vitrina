"""Imprime las versiones de torch y CUDA, la GPU y su capacidad (para el README)."""
import torch

print(f"torch: {torch.__version__}")
print(f"CUDA (torch): {torch.version.cuda}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Capacidad: sm_{torch.cuda.get_device_capability(0)[0]}{torch.cuda.get_device_capability(0)[1]}")
else:
    print("GPU: no disponible")
