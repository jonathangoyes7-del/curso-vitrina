from pathlib import Path

import pytest

from panel.cola import Cola, Estado, Trabajador
from panel.etapas import etapas_reales
from panel.ficha import Ficha
from panel.lote import GeneradorIdol
from panel.splat import leer_spz
from tests.utilidades import escribir_ply_sintetico


class SalidaFalsa:
    """Lo que devuelve Idol: un PLY de verdad (pequeño) y la imagen de entrada."""
    def __init__(self, puntos=512):
        self.puntos = puntos
        self.gaussian = self
        self.preprocessed_image = self

    def save_ply(self, ruta):
        escribir_ply_sintetico(Path(ruta), self.puntos)

    def save(self, ruta):
        Path(ruta).write_bytes(b"png")


class PipelineFalso:
    def __init__(self, error=None, puntos=512):
        self.llamadas, self.error, self.puntos = [], error, puntos

    def __call__(self, foto, **kwargs):
        self.llamadas.append((foto, kwargs))
        if self.error:
            raise RuntimeError(self.error)
        return SalidaFalsa(self.puntos)


FICHA = Ficha(nombre="Cuenco de gres", materiales="Gres", categoria="Cerámica", cuidados="Lavar a mano.")


def redactar_falso(traza=None, ficha=FICHA):
    def redactar(foto, *, url_ollama, modelo):
        if traza is not None:
            traza.append(("redactar", Path(foto).name, url_ollama, modelo))
        return ficha
    return redactar


class GeneradorTrazado(GeneradorIdol):
    def __init__(self, traza, error=None):
        super().__init__(fabrica=lambda: PipelineFalso(error=error))
        self.traza = traza

    def generar(self, *a, **k):
        self.traza.append("generar")
        return super().generar(*a, **k)

    def liberar(self):
        self.traza.append("liberar")
        super().liberar()


def pieza_con_foto(c: Cola) -> int:
    def preparar(i):
        c.carpeta_borrador(i).mkdir(parents=True)
        (c.carpeta_borrador(i) / "foto.jpg").write_bytes(b"jpg")
    return c.crear_pieza(preparar=preparar)


def test_etapa_3d_genera_ply(config_tmp):
    c, p = Cola(config_tmp), PipelineFalso()
    i = pieza_con_foto(c)
    etapas = etapas_reales(config_tmp, generador=GeneradorIdol(fabrica=lambda: p), redactar=redactar_falso())
    assert [e.nombre for e in etapas] == ["3d", "ficha"]
    Trabajador(c, etapas).procesar_uno()
    b = c.carpeta_borrador(i)
    assert c.obtener(i).estado is Estado.PARA_REVISAR
    assert (b / "pieza.ply").is_file() and (b / "entrada.png").is_file()
    assert (b / "pieza.spz").is_file() and leer_spz(b / "pieza.spz").num_gaussianos == 512
    assert not (b / "pieza.spz.tmp").exists()
    foto, kwargs = p.llamadas[0]
    assert foto == str(b / "foto.jpg")
    assert kwargs["mode"] == "real" and kwargs["num_gaussians"] == config_tmp.num_gaussianos


def test_pipeline_se_libera_tras_cada_pieza(config_tmp):
    c, cargas = Cola(config_tmp), []
    for _ in range(3):
        pieza_con_foto(c)
    gen = GeneradorIdol(fabrica=lambda: cargas.append(1) or PipelineFalso())
    t = Trabajador(c, etapas_reales(config_tmp, generador=gen, redactar=redactar_falso()))
    while t.procesar_uno():
        pass
    assert len(cargas) == 3  # se libera tras cada 3D para dejar la VRAM a Gemma
    assert all(p.estado is Estado.PARA_REVISAR for p in c.listar())


def test_fallo_de_idol_deja_error(config_tmp):
    c = Cola(config_tmp)
    i = pieza_con_foto(c)
    gen = GeneradorIdol(fabrica=lambda: PipelineFalso(error="CUDA out of memory"))
    Trabajador(c, etapas_reales(config_tmp, generador=gen, redactar=redactar_falso())).procesar_uno()
    p = c.obtener(i)
    assert p.estado is Estado.ERROR and p.error == "3d: CUDA out of memory"


def test_sin_generador_no_carga_nada_al_crear(config_tmp):
    # Crear las etapas no importa idol/torch ni carga el modelo: eso pasa en el primer trabajo.
    etapa, _ = etapas_reales(config_tmp)
    assert etapa.generador._pipeline is None


def test_orden_y_liberacion_antes_de_la_ficha(config_tmp):
    c, traza = Cola(config_tmp), []
    pieza_con_foto(c)
    etapas = etapas_reales(config_tmp, generador=GeneradorTrazado(traza), redactar=redactar_falso(traza))
    assert [e.nombre for e in etapas] == ["3d", "ficha"]
    Trabajador(c, etapas).procesar_uno()
    nombres = [t if isinstance(t, str) else t[0] for t in traza]
    assert nombres == ["generar", "liberar", "redactar"]


def test_libera_aunque_falle_3d(config_tmp):
    c, traza = Cola(config_tmp), []
    i = pieza_con_foto(c)
    etapas = etapas_reales(config_tmp, generador=GeneradorTrazado(traza, error="sin VRAM"),
                           redactar=redactar_falso(traza))
    Trabajador(c, etapas).procesar_uno()
    p = c.obtener(i)
    assert "liberar" in traza and not any(isinstance(t, tuple) for t in traza)
    assert p.estado is Estado.ERROR and p.error == "3d: sin VRAM" and p.ficha_borrador is None


def test_la_ficha_queda_en_borrador_para_revisar(config_tmp):
    c, traza = Cola(config_tmp), []
    i = pieza_con_foto(c)
    Trabajador(c, etapas_reales(config_tmp, generador=GeneradorTrazado([]),
                                redactar=redactar_falso(traza))).procesar_uno()
    p = c.obtener(i)
    assert p.estado is Estado.PARA_REVISAR
    assert p.ficha_borrador == FICHA and p.ficha_vigente is None and not p.en_sitio
    assert c.piezas_para_sitio() == []
    assert traza == [("redactar", "foto.jpg", config_tmp.url_ollama, config_tmp.modelo_ficha)]


def test_ficha_invalida_deja_error(config_tmp):
    from panel.ficha import FichaInvalida

    def redactar(foto, *, url_ollama, modelo):
        raise FichaInvalida({"categoria": "debe ser una de: Cerámica"})

    c = Cola(config_tmp)
    i = pieza_con_foto(c)
    Trabajador(c, etapas_reales(config_tmp, generador=GeneradorTrazado([]), redactar=redactar)).procesar_uno()
    p = c.obtener(i)
    assert p.estado is Estado.ERROR and p.error.startswith("ficha: ") and p.ficha_borrador is None


def test_spz_baja_gaussianos_hasta_que_cabe(config_tmp):
    from dataclasses import replace
    from panel.splat import comprimir

    # Con 8 192 puntos por intento el SPZ siempre pesa lo mismo: el límite se fija justo por debajo
    # para forzar los tres intentos y comprobar que se piden 262 144 -> 131 072 -> 65 536.
    c, p = Cola(config_tmp), PipelineFalso(puntos=8192)
    i = pieza_con_foto(c)
    peso = comprimir(escribir_ply_sintetico(config_tmp.datos / "x.ply", 8192), config_tmp.datos / "x.spz")
    cfg = replace(config_tmp, limite_spz=peso - 1)
    Trabajador(c, etapas_reales(cfg, generador=GeneradorIdol(fabrica=lambda: p), redactar=redactar_falso())).procesar_uno()
    assert [k["num_gaussians"] for _, k in p.llamadas] == [262_144, 131_072, 65_536]
    pieza = c.obtener(i)
    assert pieza.estado is Estado.ERROR and "supera el límite" in pieza.error
    assert not (c.carpeta_borrador(i) / "pieza.spz").exists() and pieza.ficha_borrador is None


def test_spz_pasa_a_la_segunda_cantidad(config_tmp):
    from dataclasses import replace
    from panel.splat import comprimir

    c = Cola(config_tmp)
    i = pieza_con_foto(c)
    pesos = {}

    class PipelineDecreciente(PipelineFalso):
        def __call__(self, foto, **kw):   # menos gaussianos pedidos -> menos puntos
            self.puntos = kw["num_gaussians"] // 64
            return super().__call__(foto, **kw)

    for n in (262_144, 131_072):
        pesos[n] = comprimir(escribir_ply_sintetico(config_tmp.datos / f"{n}.ply", n // 64), config_tmp.datos / f"{n}.spz")
    cfg = replace(config_tmp, limite_spz=(pesos[262_144] + pesos[131_072]) // 2)
    p = PipelineDecreciente()
    Trabajador(c, etapas_reales(cfg, generador=GeneradorIdol(fabrica=lambda: p), redactar=redactar_falso())).procesar_uno()
    assert [k["num_gaussians"] for _, k in p.llamadas] == [262_144, 131_072]
    assert c.obtener(i).estado is Estado.PARA_REVISAR
    assert leer_spz(c.carpeta_borrador(i) / "pieza.spz").num_gaussianos == 131_072 // 64
