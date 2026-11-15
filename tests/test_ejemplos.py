import json
import shutil
from pathlib import Path

from panel.cola import Cola, Estado
from panel.ejemplos import RUTA_JSON, cargar_ejemplos
from panel.ficha import CATEGORIAS

FOTO = Path(__file__).resolve().parent.parent / "fotos" / "vaso_ceramica.jpg"  # solo lectura


def test_json_valido():
    e = json.loads(Path("ejemplos/ejemplos.json").read_text(encoding="utf-8"))
    assert sorted(x["categoria"] for x in e) == sorted(CATEGORIAS)
    assert all(x["autor"] and x["enlace"].startswith("https://unsplash.com/") for x in e)


def test_cargar_crea_tres_ejemplos(config_tmp):
    descargadas = []

    def descargar_falso(url, destino):
        descargadas.append(url)
        shutil.copy(FOTO, destino)
        return destino

    cola = Cola(config_tmp)
    ids = cargar_ejemplos(cola, RUTA_JSON, descargar_falso)
    assert len(ids) == 3 and len(descargadas) == 3
    autores = {x["autor"] for x in json.loads(RUTA_JSON.read_text(encoding="utf-8"))}
    for i in ids:
        p = cola.obtener(i)
        assert p.es_ejemplo and p.estado == Estado.PENDIENTE
        assert p.credito_autor in autores and p.credito_url.startswith("https://unsplash.com/")
        assert (cola.carpeta_borrador(i) / "foto.jpg").is_file()
    assert not list(config_tmp.datos.glob(".ejemplos-*"))  # sin temporales
    assert FOTO.is_file()  # el original no se tocó
    cola.cerrar()
