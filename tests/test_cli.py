import json
import shutil

from fantasy.cli import main

AHORA = "2026-09-25T02:26:00+00:00"
ENTORNO = {"NTFY_TOPIC": "t", "NTFY_EMAIL": "yo@example.com", "PAGES_URL": "https://p/"}


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
    # Revisión final: ntfy caído no debe tumbar la publicación.
    def falla(*a, **k):
        raise OSError("ntfy no responde")

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
