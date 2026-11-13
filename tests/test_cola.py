import threading

import pytest

from panel.cola import (Cola, ContextoTrabajo, Estado, Trabajador, TransicionInvalida,
                        transicion)


class EtapaFalsa:
    def __init__(self, nombre="3d", error=None, traza=None):
        self.nombre, self.error, self.traza = nombre, error, traza

    def __call__(self, ctx: ContextoTrabajo) -> None:
        if self.traza is not None:
            self.traza.append((self.nombre, ctx.pieza.id, ctx.pieza.estado))
        if self.error:
            raise RuntimeError(self.error)
        (ctx.borrador / "pieza.spz").write_bytes(b"spz")
        (ctx.borrador / "pieza.ply").write_bytes(b"ply")


def procesar_con_etapas_falsas(c: Cola, i: int) -> None:
    assert Trabajador(c, [EtapaFalsa()]).procesar_uno()
    assert c.obtener(i).estado is Estado.PARA_REVISAR


def pieza_publicada(config):
    c = Cola(config)
    i = c.crear_pieza()
    procesar_con_etapas_falsas(c, i)
    c.aprobar(i)
    assert c.marcar_publicadas() == 1
    return c, i


def test_tabla_de_transiciones():
    assert transicion(Estado.PENDIENTE, "empezar") is Estado.PROCESANDO
    assert transicion(Estado.PROCESANDO, "terminar") is Estado.PARA_REVISAR
    assert transicion(Estado.PROCESANDO, "fallar") is Estado.ERROR
    assert transicion(Estado.ERROR, "reintentar") is Estado.PENDIENTE
    assert transicion(Estado.APROBADA, "despublicar") is Estado.DESPUBLICADA
    assert transicion(Estado.DESPUBLICADA, "aprobar") is Estado.APROBADA
    with pytest.raises(TransicionInvalida):
        transicion(Estado.PENDIENTE, "aprobar")
    with pytest.raises(TransicionInvalida):
        transicion(Estado.PROCESANDO, "publicar")
    with pytest.raises(TransicionInvalida):
        transicion(Estado.PUBLICADA, "aprobar")


def test_estados_exactos():
    assert [e.value for e in Estado] == ["pendiente", "procesando", "para revisar", "aprobada",
                                         "publicada", "despublicada", "error"]


def test_crear_y_listar(config_tmp):
    c = Cola(config_tmp)
    a = c.crear_pieza()
    b = c.crear_pieza(es_ejemplo=True, credito_autor="Ana", credito_url="https://unsplash.com/x")
    assert [p.id for p in c.listar()] == [b, a]
    p = c.obtener(b)
    assert p.estado is Estado.PENDIENTE and p.es_ejemplo and p.credito_autor == "Ana"
    assert p.slug is None and not p.slug_fijo and not p.en_sitio and p.error is None
    assert c.carpeta_borrador(b) == config_tmp.carpeta_piezas / str(b) / "borrador"
    assert c.carpeta_vigente(b) == config_tmp.carpeta_piezas / str(b) / "vigente"
    with pytest.raises(KeyError):
        c.obtener(999)
    assert (config_tmp.datos / "vitrina.sqlite").is_file()


def test_crear_pieza_preparar_falla_no_deja_fila(config_tmp):
    c = Cola(config_tmp)

    def preparar(i):
        raise OSError("disco lleno")

    with pytest.raises(OSError):
        c.crear_pieza(preparar=preparar)
    assert c.listar() == []


def test_nada_entra_al_sitio_sin_aprobar(config_tmp):
    c = Cola(config_tmp)
    i = c.crear_pieza()
    procesar_con_etapas_falsas(c, i)
    assert c.obtener(i).estado is Estado.PARA_REVISAR and c.piezas_para_sitio() == []


def test_aprobar_copia_borrador_sin_ply(config_tmp):
    c = Cola(config_tmp)
    i = c.crear_pieza()
    procesar_con_etapas_falsas(c, i)
    c.aprobar(i)
    p = c.obtener(i)
    assert p.estado is Estado.APROBADA and p.en_sitio and p.slug_fijo
    assert (c.carpeta_vigente(i) / "pieza.spz").is_file()
    assert not (c.carpeta_vigente(i) / "pieza.ply").exists()
    assert [x.id for x in c.piezas_para_sitio()] == [i]


def test_editar_publicada_mantiene_vigente(config_tmp):
    # Tarea 7: con Ficha, usar editar_ficha y comprobar ficha_vigente.nombre.
    c, i = pieza_publicada(config_tmp)
    assert c.aplicar(i, "editar") is Estado.PARA_REVISAR
    assert c.obtener(i).estado is Estado.PARA_REVISAR
    assert [x.id for x in c.piezas_para_sitio()] == [i]


def test_despublicada_editada_no_vuelve(config_tmp):
    c, i = pieza_publicada(config_tmp)
    c.despublicar(i)
    c.aplicar(i, "editar")
    assert c.piezas_para_sitio() == []


def test_recuperar_interrumpidos(config_tmp):
    c = Cola(config_tmp)
    i = c.crear_pieza()
    c.tomar_siguiente()
    assert Cola(config_tmp).recuperar_interrumpidos() == 1
    assert c.obtener(i).estado is Estado.PENDIENTE


def test_tomar_siguiente_la_mas_antigua(config_tmp):
    c = Cola(config_tmp)
    a, b = c.crear_pieza(), c.crear_pieza()
    p = c.tomar_siguiente()
    assert p.id == a and p.estado is Estado.PROCESANDO
    assert c.tomar_siguiente().id == b
    assert c.tomar_siguiente() is None


def test_un_trabajo_a_la_vez(config_tmp):
    c = Cola(config_tmp)
    c.crear_pieza()
    barrera, recibidas = threading.Barrier(2), []

    def tomar():
        barrera.wait()
        recibidas.append(c.tomar_siguiente())

    hilos = [threading.Thread(target=tomar) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert sum(p is not None for p in recibidas) == 1


def test_error_y_reintento(config_tmp):
    c = Cola(config_tmp)
    i = c.crear_pieza()
    assert Trabajador(c, [EtapaFalsa("3d", error="sin VRAM")]).procesar_uno()
    p = c.obtener(i)
    assert p.estado is Estado.ERROR and p.error == "3d: sin VRAM"
    assert c.aplicar(i, "reintentar") is Estado.PENDIENTE
    assert c.obtener(i).error is None


def test_trabajador_etapas_en_orden(config_tmp):
    c = Cola(config_tmp)
    i = c.crear_pieza()
    traza = []
    t = Trabajador(c, [EtapaFalsa("3d", traza=traza), EtapaFalsa("ficha", traza=traza)])
    assert t.procesar_uno() is True
    assert traza == [("3d", i, Estado.PROCESANDO), ("ficha", i, Estado.PROCESANDO)]
    assert t.procesar_uno() is False


def test_trabajador_en_hilo(config_tmp):
    c = Cola(config_tmp)
    i = c.crear_pieza()
    c.tomar_siguiente()  # simula un cierre a mitad de trabajo
    hecho = threading.Event()

    class Avisa(EtapaFalsa):
        def __call__(self, ctx):
            super().__call__(ctx)
            hecho.set()

    t = Trabajador(c, [Avisa()])
    t.iniciar()
    try:
        assert hecho.wait(5)
    finally:
        t.detener()
    assert c.obtener(i).estado is Estado.PARA_REVISAR


def test_borrar_quita_carpeta(config_tmp):
    c = Cola(config_tmp)
    i = c.crear_pieza()
    c.carpeta_borrador(i).mkdir(parents=True)
    c.tomar_siguiente()
    with pytest.raises(TransicionInvalida):
        c.borrar(i)
    c.marcar_error(i, "x")
    c.borrar(i)
    assert not (config_tmp.carpeta_piezas / str(i)).exists()
    with pytest.raises(KeyError):
        c.obtener(i)


def test_despublicada_vuelve_al_aprobar(config_tmp):
    c = Cola(config_tmp)
    i = c.crear_pieza()
    procesar_con_etapas_falsas(c, i)
    c.aprobar(i)
    c.despublicar(i)
    assert c.obtener(i).estado is Estado.DESPUBLICADA and not c.obtener(i).en_sitio
    c.aprobar(i)  # tiene vigente/: vuelve
    assert c.obtener(i).en_sitio


def test_segundo_trabajador_no_arranca(config_tmp):
    # Dos paneles sobre los mismos datos: el segundo no puede tocar la cola ni la GPU.
    c = Cola(config_tmp)
    primero = Trabajador(c, [])
    primero.iniciar()
    try:
        i = c.crear_pieza()
        c.tomar_siguiente()  # la está procesando el primer panel
        segundo = Trabajador(Cola(config_tmp), [])
        with pytest.raises(RuntimeError, match="otro panel"):
            segundo.iniciar()
        assert c.obtener(i).estado is Estado.PROCESANDO
    finally:
        primero.detener()


def test_detener_no_olvida_un_hilo_vivo(config_tmp):
    c = Cola(config_tmp)
    c.crear_pieza()
    dentro, soltar = threading.Event(), threading.Event()

    class Lenta(EtapaFalsa):
        def __call__(self, ctx):
            dentro.set()
            soltar.wait(5)

    t = Trabajador(c, [Lenta()])
    t.iniciar()
    assert dentro.wait(5)
    hilo = t._hilo
    t.detener(espera=0.05)
    t.iniciar()
    assert t._hilo is hilo and threading.active_count() >= 2
    soltar.set()
    t.detener()
    assert t._hilo is None
