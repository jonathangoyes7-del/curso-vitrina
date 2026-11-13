from pathlib import Path

from panel.cola import Cola, Estado, Trabajador
from panel.etapas import etapas_reales
from panel.lote import GeneradorIdol


class SalidaFalsa:
    class gaussian:
        @staticmethod
        def save_ply(ruta):
            Path(ruta).write_bytes(b"ply")

    class preprocessed_image:
        @staticmethod
        def save(ruta):
            Path(ruta).write_bytes(b"png")


class PipelineFalso:
    def __init__(self, error=None):
        self.llamadas, self.error = [], error

    def __call__(self, foto, **kwargs):
        self.llamadas.append((foto, kwargs))
        if self.error:
            raise RuntimeError(self.error)
        return SalidaFalsa()


def pieza_con_foto(c: Cola) -> int:
    def preparar(i):
        c.carpeta_borrador(i).mkdir(parents=True)
        (c.carpeta_borrador(i) / "foto.jpg").write_bytes(b"jpg")
    return c.crear_pieza(preparar=preparar)


def test_etapa_3d_genera_ply(config_tmp):
    c, p = Cola(config_tmp), PipelineFalso()
    i = pieza_con_foto(c)
    etapas = etapas_reales(config_tmp, generador=GeneradorIdol(fabrica=lambda: p))
    assert [e.nombre for e in etapas] == ["3d"]
    Trabajador(c, etapas).procesar_uno()
    b = c.carpeta_borrador(i)
    assert c.obtener(i).estado is Estado.PARA_REVISAR
    assert (b / "pieza.ply").is_file() and (b / "entrada.png").is_file()
    foto, kwargs = p.llamadas[0]
    assert foto == str(b / "foto.jpg")
    assert kwargs["mode"] == "real" and kwargs["num_gaussians"] == config_tmp.num_gaussianos


def test_pipeline_se_carga_una_sola_vez(config_tmp):
    c, cargas = Cola(config_tmp), []
    for _ in range(3):
        pieza_con_foto(c)
    gen = GeneradorIdol(fabrica=lambda: cargas.append(1) or PipelineFalso())
    t = Trabajador(c, etapas_reales(config_tmp, generador=gen))
    while t.procesar_uno():
        pass
    assert len(cargas) == 1
    assert all(p.estado is Estado.PARA_REVISAR for p in c.listar())


def test_fallo_de_idol_deja_error(config_tmp):
    c = Cola(config_tmp)
    i = pieza_con_foto(c)
    gen = GeneradorIdol(fabrica=lambda: PipelineFalso(error="CUDA out of memory"))
    Trabajador(c, etapas_reales(config_tmp, generador=gen)).procesar_uno()
    p = c.obtener(i)
    assert p.estado is Estado.ERROR and p.error == "3d: CUDA out of memory"


def test_sin_generador_no_carga_nada_al_crear(config_tmp):
    # Crear las etapas no importa idol/torch ni carga el modelo: eso pasa en el primer trabajo.
    (etapa,) = etapas_reales(config_tmp)
    assert etapa.generador._pipeline is None
