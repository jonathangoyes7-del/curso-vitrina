import pytest

pytestmark = pytest.mark.gpu


def test_cuda_blackwell():
    import torch

    assert torch.cuda.is_available()
    mayor, menor = map(int, torch.version.cuda.split(".")[:2])
    assert (mayor, menor) >= (12, 8)
    assert torch.cuda.get_device_capability(0) == (12, 0)
    assert "5060 Ti" in torch.cuda.get_device_name(0)
    a = torch.randn(1024, 1024, device="cuda")
    assert torch.isfinite(a @ a).all()
