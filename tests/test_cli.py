import json
import shutil

from fantasy.cli import main

AHORA = "2026-09-25T02:26:00+00:00"
ENTORNO = {"GMAIL_USER": "yo@gmail.com", "GMAIL_APP_PASSWORD": "clave",
           "CORREO_DESTINO": "yo@example.com", "PAGES_URL": "https://p/"}


def _args(fixture_dir, salida, *extra):
    return ["reporte", "--tipo", "viernes", "--instantanea", str(fixture_dir),
            "--salida", str(salida), "--ahora", AHORA, *extra]


def test_corrida_completa_sin_red(fixture_dir, tmp_path):
    enviados = []
    codigo = main(_args(fixture_dir, tmp_path), entorno=ENTORNO,
                  enviar_fn=lambda *a, **k: enviados.append(a))
    assert codigo == 0
    html = (tmp_path / "reportes" / "2026-sem03-viernes.html").read_text(encoding="utf-8")
    assert "SIN VALIDAR" in html
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == html
    assert len(enviados) == 1
    assert enviados[0][0] == ("yo@gmail.com", "clave")
    assert enviados[0][1] == "yo@example.com"
    assert enviados[0][4] == "https://p/reportes/2026-sem03-viernes.html"


def test_segunda_corrida_no_repite_ni_reenvia(fixture_dir, tmp_path):
    # Review Focus 5
    enviados = []
    envio = lambda *a, **k: enviados.append(a)
    assert main(_args(fixture_dir, tmp_path), entorno=ENTORNO, enviar_fn=envio) == 0
    destino = tmp_path / "reportes" / "2026-sem03-viernes.html"
    antes = destino.stat().st_mtime_ns
    assert main(_args(fixture_dir, tmp_path), entorno=ENTORNO, enviar_fn=envio) == 0
    assert destino.stat().st_mtime_ns == antes
    assert len(enviados) == 1


def test_auto_fuera_de_horario_no_hace_nada(fixture_dir, tmp_path):
    codigo = main(["reporte", "--tipo", "auto", "--instantanea", str(fixture_dir),
                   "--salida", str(tmp_path), "--ahora", "2026-09-30T09:00:00+00:00"],
                  entorno={}, enviar_fn=None)
    assert codigo == 0
    assert not (tmp_path / "reportes").exists()


def test_datos_invalidos_avisan_y_salen_con_error(fixture_dir, tmp_path):
    roto = tmp_path / "roto"
    shutil.copytree(fixture_dir, roto)
    liga = json.loads((roto / "liga.json").read_text(encoding="utf-8"))
    liga["teams"] = liga["teams"][:7]
    (roto / "liga.json").write_text(json.dumps(liga), encoding="utf-8")
    enviados = []
    codigo = main(_args(roto, tmp_path / "out"), entorno=ENTORNO,
                  enviar_fn=lambda *a, **k: enviados.append(a))
    assert codigo == 1
    assert "NO generado" in enviados[0][2]
    assert not (tmp_path / "out" / "reportes").exists()


def test_temporada_terminada_sale_limpio(fixture_dir, tmp_path, monkeypatch):
    from fantasy.reporte import armado

    def terminada(*a, **k):
        raise armado.TemporadaTerminada("la temporada terminó")

    monkeypatch.setattr("fantasy.cli.armar", terminada)
    enviados = []
    codigo = main(_args(fixture_dir, tmp_path), entorno=ENTORNO,
                  enviar_fn=lambda *a, **k: enviados.append(a))
    assert codigo == 0 and enviados == []


def test_si_falla_el_correo_el_reporte_igual_se_publica(fixture_dir, tmp_path):
    # Revisión final: correo caído no debe tumbar la publicación.
    def falla(*a, **k):
        raise OSError("Gmail no responde")

    codigo = main(_args(fixture_dir, tmp_path), entorno=ENTORNO, enviar_fn=falla)
    assert codigo == 0
    assert (tmp_path / "reportes" / "2026-sem03-viernes.html").exists()


def test_error_inesperado_avisa_y_sale_con_error(fixture_dir, tmp_path, monkeypatch):
    # Revisión final: cualquier error, no solo DatosInvalidos, tiene que avisar.
    def roto(*a, **k):
        raise KeyError("columna que ESPN renombró")

    monkeypatch.setattr("fantasy.cli.armar", roto)
    enviados = []
    codigo = main(_args(fixture_dir, tmp_path), entorno=ENTORNO,
                  enviar_fn=lambda *a, **k: enviados.append(a))
    assert codigo == 1
    assert "NO generado" in enviados[0][2]


def test_auto_no_descarga_otra_vez_si_ya_se_genero_en_esta_ventana(fixture_dir, tmp_path):
    # Con corridas cada media hora, solo la primera de la ventana trabaja.
    args = ["reporte", "--tipo", "auto", "--instantanea", str(fixture_dir),
            "--salida", str(tmp_path), "--sin-correo"]
    assert main([*args, "--ahora", "2026-09-29T09:07:00+00:00"], entorno={}) == 0
    assert (tmp_path / "ultimo_martes.txt").exists()
    otra = tmp_path / "vacia"
    otra.mkdir()
    # Si intentara cargar datos de esta carpeta vacía fallaría: debe saltarse antes.
    args[4] = str(otra)
    assert main([*args, "--ahora", "2026-09-29T14:48:00+00:00"], entorno={}) == 0
