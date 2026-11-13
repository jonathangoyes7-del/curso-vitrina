def test_config_por_defecto():
    from panel.config import Config

    c = Config.por_defecto()
    assert c.host == "127.0.0.1" and c.puerto == 8765
    assert c.url_publica.endswith("/curso-vitrina/")
    assert c.datos.name == "datos" and c.sitio.name == "sitio"
