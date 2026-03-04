from flask import Flask, render_template_string, redirect, url_for
import requests
import datetime
import statistics
import sqlite3
import os

app = Flask(__name__)


# Chemin de la BDD SQLite

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "monitoring.db")


# Init BDD

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS executions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            executed_at  TEXT    NOT NULL,
            total        INTEGER NOT NULL,
            passed       INTEGER NOT NULL,
            failed       INTEGER NOT NULL,
            success_rate REAL    NOT NULL,
            avg_ms       REAL,
            min_ms       REAL,
            max_ms       REAL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS test_results (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id INTEGER NOT NULL,
            test_id      TEXT    NOT NULL,
            test_name    TEXT    NOT NULL,
            status       TEXT    NOT NULL,
            http_code    INTEGER,
            response_ms  REAL,
            error        TEXT,
            FOREIGN KEY (execution_id) REFERENCES executions(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


# Configuration des tests Open-Meteo

BASE_URL = "https://api.open-meteo.com/v1/forecast"

TESTS_CONFIG = [
    {
        "id": "TC-01",
        "name": "Statut HTTP 200",
        "description": "L'API doit répondre avec un code HTTP 200",
        "params": {"latitude": 48.8566, "longitude": 2.3522, "current_weather": True},
        "check": lambda r: r.status_code == 200,
        "expected": "200 OK"
    },
    {
        "id": "TC-02",
        "name": "Présence du champ 'current_weather'",
        "description": "La réponse JSON doit contenir la clé 'current_weather'",
        "params": {"latitude": 48.8566, "longitude": 2.3522, "current_weather": True},
        "check": lambda r: "current_weather" in r.json(),
        "expected": "Clé 'current_weather' présente"
    },
    {
        "id": "TC-03",
        "name": "Température dans une plage réaliste",
        "description": "La température doit être comprise entre -60°C et +60°C",
        "params": {"latitude": 48.8566, "longitude": 2.3522, "current_weather": True},
        "check": lambda r: -60 <= r.json()["current_weather"]["temperature"] <= 60,
        "expected": "Température entre -60°C et +60°C"
    },
    {
        "id": "TC-04",
        "name": "Coordonnées GPS valides (New York)",
        "description": "L'API doit fonctionner pour des coordonnées différentes",
        "params": {"latitude": 40.7128, "longitude": -74.0060, "current_weather": True},
        "check": lambda r: r.status_code == 200 and "current_weather" in r.json(),
        "expected": "200 OK avec current_weather"
    },
    {
        "id": "TC-05",
        "name": "Champ 'windspeed' présent",
        "description": "La vitesse du vent doit être fournie dans current_weather",
        "params": {"latitude": 48.8566, "longitude": 2.3522, "current_weather": True},
        "check": lambda r: "windspeed" in r.json().get("current_weather", {}),
        "expected": "Clé 'windspeed' présente"
    },
    {
        "id": "TC-06",
        "name": "Temps de réponse < 3s",
        "description": "L'API doit répondre en moins de 3 secondes",
        "params": {"latitude": 48.8566, "longitude": 2.3522, "current_weather": True},
        "check": lambda r: r.elapsed.total_seconds() < 3,
        "expected": "Temps de réponse < 3000 ms"
    },
    {
        "id": "TC-07",
        "name": "Prévisions horaires disponibles",
        "description": "L'API doit retourner des données horaires si demandées",
        "params": {"latitude": 48.8566, "longitude": 2.3522, "hourly": "temperature_2m"},
        "check": lambda r: "hourly" in r.json() and "temperature_2m" in r.json()["hourly"],
        "expected": "Données horaires 'temperature_2m' présentes"
    },
    {
        "id": "TC-08",
        "name": "Coordonnées invalides → erreur gérée",
        "description": "L'API doit gérer proprement des coordonnées hors limites",
        "params": {"latitude": 9999, "longitude": 9999, "current_weather": True},
        "check": lambda r: r.status_code in [400, 422],
        "expected": "Code 400 ou 422 (erreur attendue)"
    },
]


# Exécution des tests + sauvegarde SQLite

def run_and_save_tests():
    results = []
    response_times = []

    for test in TESTS_CONFIG:
        result = {
            "id": test["id"], "name": test["name"],
            "description": test["description"], "expected": test["expected"],
            "status": "FAIL", "response_time_ms": None,
            "http_code": None, "error": None,
        }
        try:
            resp = requests.get(BASE_URL, params=test["params"], timeout=10)
            elapsed_ms = resp.elapsed.total_seconds() * 1000
            result["response_time_ms"] = round(elapsed_ms, 1)
            result["http_code"] = resp.status_code
            response_times.append(elapsed_ms)
            result["status"] = "PASS" if test["check"](resp) else "FAIL"
        except requests.exceptions.Timeout:
            result["error"] = "Timeout"
        except Exception as e:
            result["error"] = str(e)[:500]
        results.append(result)

    total   = len(results)
    passed  = sum(1 for r in results if r["status"] == "PASS")
    failed  = total - passed
    success = round((passed / total) * 100, 1) if total > 0 else 0
    avg_ms  = round(statistics.mean(response_times), 1) if response_times else None
    min_ms  = round(min(response_times), 1) if response_times else None
    max_ms  = round(max(response_times), 1) if response_times else None
    now     = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M:%S")

    qos = {
        "total": total, "passed": passed, "failed": failed,
        "success_rate": success,
        "avg_response_ms": avg_ms or "N/A",
        "min_response_ms": min_ms or "N/A",
        "max_response_ms": max_ms or "N/A",
        "timestamp": now,
    }

    # Sauvegarde SQLite
    try:
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO executions (executed_at, total, passed, failed, success_rate, avg_ms, min_ms, max_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.datetime.now().isoformat(), total, passed, failed, success, avg_ms, min_ms, max_ms))
        exec_id = cur.lastrowid
        for r in results:
            cur.execute("""
                INSERT INTO test_results (execution_id, test_id, test_name, status, http_code, response_ms, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (exec_id, r["id"], r["name"], r["status"], r["http_code"], r["response_time_ms"], r["error"]))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] {e}")

    return results, qos


def get_history():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT id, executed_at, total, passed, failed, success_rate, avg_ms
            FROM executions ORDER BY executed_at DESC LIMIT 10
        """)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return []


def get_execution_details(exec_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM executions WHERE id = ?", (exec_id,))
        execution = dict(cur.fetchone())
        cur.execute("SELECT * FROM test_results WHERE execution_id = ? ORDER BY test_id", (exec_id,))
        results = [dict(r) for r in cur.fetchall()]
        conn.close()
        return execution, results
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return None, []


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>API Monitor — Open-Meteo</title>
  <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet"/>
  <style>
    :root { --bg:#0b0f1a; --surface:#111827; --surface2:#1a2236; --accent:#38bdf8; --accent2:#818cf8; --green:#34d399; --red:#f87171; --yellow:#fbbf24; --text:#e2e8f0; --muted:#64748b; --border:#1e2d42; }
    * { box-sizing:border-box; margin:0; padding:0; }
    body { background:var(--bg); color:var(--text); font-family:'Syne',sans-serif; min-height:100vh; padding:2rem 1.5rem 4rem; }
    body::before { content:''; position:fixed; inset:0; background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E"); pointer-events:none; z-index:0; opacity:.4; }
    .container { max-width:1100px; margin:0 auto; position:relative; z-index:1; }
    header { display:flex; flex-direction:column; gap:.4rem; margin-bottom:2.5rem; border-left:4px solid var(--accent); padding-left:1.2rem; }
    header .label { font-family:'Space Mono',monospace; font-size:.7rem; color:var(--accent); letter-spacing:.2em; text-transform:uppercase; }
    header h1 { font-size:2.2rem; font-weight:800; background:linear-gradient(90deg,#38bdf8,#818cf8); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
    header .meta { font-family:'Space Mono',monospace; font-size:.72rem; color:var(--muted); }
    .btn { display:inline-flex; align-items:center; gap:.5rem; padding:.6rem 1.4rem; border-radius:8px; font-family:'Space Mono',monospace; font-size:.75rem; font-weight:700; cursor:pointer; text-decoration:none; border:none; transition:all .2s; }
    .btn-primary { background:linear-gradient(90deg,var(--accent),var(--accent2)); color:#0b0f1a; }
    .btn-primary:hover { opacity:.85; transform:translateY(-1px); }
    .btn-secondary { background:var(--surface2); color:var(--text); border:1px solid var(--border); }
    .btn-secondary:hover { border-color:var(--accent); }
    .actions { display:flex; gap:1rem; margin-bottom:2.5rem; flex-wrap:wrap; }
    .qos-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(155px,1fr)); gap:1rem; margin-bottom:2.5rem; }
    .card { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:1.2rem 1rem; display:flex; flex-direction:column; gap:.4rem; transition:transform .2s,border-color .2s; }
    .card:hover { transform:translateY(-2px); border-color:var(--accent); }
    .card-label { font-family:'Space Mono',monospace; font-size:.65rem; color:var(--muted); text-transform:uppercase; letter-spacing:.1em; }
    .card-value { font-size:1.9rem; font-weight:800; line-height:1; }
    .card-unit { font-size:.75rem; color:var(--muted); font-family:'Space Mono',monospace; }
    .accent-blue{color:var(--accent)} .accent-green{color:var(--green)} .accent-red{color:var(--red)} .accent-indigo{color:var(--accent2)} .accent-yellow{color:var(--yellow)}
    .progress-wrap { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:1.2rem 1.5rem; margin-bottom:2.5rem; }
    .progress-wrap h2 { font-size:.85rem; font-family:'Space Mono',monospace; color:var(--muted); text-transform:uppercase; letter-spacing:.1em; margin-bottom:.8rem; }
    .progress-bar-bg { background:var(--surface2); border-radius:999px; height:12px; overflow:hidden; }
    .progress-bar-fill { height:100%; border-radius:999px; background:linear-gradient(90deg,var(--green),var(--accent)); }
    .progress-labels { display:flex; justify-content:space-between; margin-top:.5rem; font-family:'Space Mono',monospace; font-size:.7rem; color:var(--muted); }
    .table-wrap { background:var(--surface); border:1px solid var(--border); border-radius:12px; overflow:hidden; margin-bottom:2.5rem; }
    .table-wrap h2 { font-size:1rem; font-weight:700; padding:1.2rem 1.5rem; border-bottom:1px solid var(--border); display:flex; align-items:center; gap:.6rem; }
    .dot { width:8px; height:8px; background:var(--accent); border-radius:50%; display:inline-block; box-shadow:0 0 8px var(--accent); }
    table { width:100%; border-collapse:collapse; }
    thead th { font-family:'Space Mono',monospace; font-size:.65rem; text-transform:uppercase; letter-spacing:.1em; color:var(--muted); padding:.8rem 1rem; text-align:left; border-bottom:1px solid var(--border); background:var(--surface2); }
    tbody tr { border-bottom:1px solid var(--border); transition:background .15s; }
    tbody tr:last-child { border-bottom:none; }
    tbody tr:hover { background:var(--surface2); }
    tbody td { padding:.85rem 1rem; font-size:.88rem; vertical-align:top; }
    .id-col { font-family:'Space Mono',monospace; font-size:.72rem; color:var(--accent2); }
    .time-col { font-family:'Space Mono',monospace; font-size:.78rem; color:var(--yellow); }
    .http-col { font-family:'Space Mono',monospace; font-size:.78rem; }
    .muted-col { color:var(--muted); font-size:.8rem; }
    .badge { display:inline-flex; align-items:center; gap:.35rem; padding:.25rem .75rem; border-radius:999px; font-family:'Space Mono',monospace; font-size:.7rem; font-weight:700; }
    .badge-pass { background:rgba(52,211,153,.12); color:var(--green); border:1px solid rgba(52,211,153,.3); }
    .badge-fail { background:rgba(248,113,113,.12); color:var(--red); border:1px solid rgba(248,113,113,.3); }
    .badge::before { content:''; width:6px; height:6px; border-radius:50%; background:currentColor; }
    footer { margin-top:3rem; text-align:center; font-family:'Space Mono',monospace; font-size:.65rem; color:var(--muted); letter-spacing:.08em; }
  </style>
</head>
<body>
<div class="container">
  <header>
    <span class="label">⚡ API Quality Monitor</span>
    <h1>Open-Meteo Test Suite</h1>
    <span class="meta">{{ qos.timestamp }} &nbsp;·&nbsp; {{ qos.total }} tests</span>
  </header>
  <div class="actions">
    <a href="/run" class="btn btn-primary">▶ Lancer les tests</a>
    <a href="/history" class="btn btn-secondary">🕓 Voir l'historique</a>
  </div>
  <div class="qos-grid">
    <div class="card"><span class="card-label">Taux de succès</span><span class="card-value accent-green">{{ qos.success_rate }}<span style="font-size:1rem">%</span></span><span class="card-unit">QoS globale</span></div>
    <div class="card"><span class="card-label">Tests passés</span><span class="card-value accent-green">{{ qos.passed }}</span><span class="card-unit">sur {{ qos.total }} tests</span></div>
    <div class="card"><span class="card-label">Tests échoués</span><span class="card-value accent-red">{{ qos.failed }}</span><span class="card-unit">erreurs détectées</span></div>
    <div class="card"><span class="card-label">Temps moyen</span><span class="card-value accent-yellow">{{ qos.avg_response_ms }}</span><span class="card-unit">ms</span></div>
    <div class="card"><span class="card-label">Temps min</span><span class="card-value accent-blue">{{ qos.min_response_ms }}</span><span class="card-unit">ms</span></div>
    <div class="card"><span class="card-label">Temps max</span><span class="card-value accent-indigo">{{ qos.max_response_ms }}</span><span class="card-unit">ms</span></div>
  </div>
  <div class="progress-wrap">
    <h2>Taux de réussite global</h2>
    <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{{ qos.success_rate }}%"></div></div>
    <div class="progress-labels"><span>0%</span><span style="color:var(--green);font-weight:700">{{ qos.success_rate }}%</span><span>100%</span></div>
  </div>
  <div class="table-wrap">
    <h2><span class="dot"></span> Résultats des tests</h2>
    <table>
      <thead><tr><th>ID</th><th>Nom du test</th><th>Description</th><th>Valeur attendue</th><th>HTTP</th><th>Temps</th><th>Statut</th></tr></thead>
      <tbody>
        {% for r in results %}
        <tr>
          <td class="id-col">{{ r.id }}</td>
          <td><strong>{{ r.name }}</strong></td>
          <td class="muted-col">{{ r.description }}</td>
          <td class="muted-col" style="font-family:'Space Mono',monospace;font-size:.7rem">{{ r.expected }}</td>
          <td class="http-col"><span style="color:{% if r.http_code == 200 %}var(--green){% elif r.http_code and r.http_code < 400 %}var(--yellow){% else %}var(--red){% endif %}">{{ r.http_code or '—' }}</span></td>
          <td class="time-col">{% if r.response_time_ms %}{{ r.response_time_ms }} ms{% else %}—{% endif %}</td>
          <td><span class="badge badge-{{ r.status|lower }}">{{ r.status }}</span></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  <footer>API MONITOR &nbsp;·&nbsp; OPEN-METEO &nbsp;·&nbsp; SQLITE &nbsp;·&nbsp; PYTHONANYWHERE</footer>
</div>
</body>
</html>
"""

HISTORY_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8"/>
  <title>Historique — Open-Meteo Monitor</title>
  <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet"/>
  <style>
    :root { --bg:#0b0f1a; --surface:#111827; --surface2:#1a2236; --accent:#38bdf8; --accent2:#818cf8; --green:#34d399; --red:#f87171; --yellow:#fbbf24; --text:#e2e8f0; --muted:#64748b; --border:#1e2d42; }
    * { box-sizing:border-box; margin:0; padding:0; }
    body { background:var(--bg); color:var(--text); font-family:'Syne',sans-serif; min-height:100vh; padding:2rem 1.5rem 4rem; }
    .container { max-width:1000px; margin:0 auto; }
    header { border-left:4px solid var(--accent); padding-left:1.2rem; margin-bottom:2.5rem; }
    header .label { font-family:'Space Mono',monospace; font-size:.7rem; color:var(--accent); letter-spacing:.2em; text-transform:uppercase; }
    header h1 { font-size:2rem; font-weight:800; background:linear-gradient(90deg,#38bdf8,#818cf8); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
    .btn { display:inline-flex; align-items:center; padding:.6rem 1.4rem; border-radius:8px; font-family:'Space Mono',monospace; font-size:.75rem; font-weight:700; text-decoration:none; background:var(--surface2); color:var(--text); border:1px solid var(--border); margin-bottom:2rem; transition:border-color .2s; }
    .btn:hover { border-color:var(--accent); }
    .table-wrap { background:var(--surface); border:1px solid var(--border); border-radius:12px; overflow:hidden; }
    .table-wrap h2 { font-size:1rem; font-weight:700; padding:1.2rem 1.5rem; border-bottom:1px solid var(--border); display:flex; align-items:center; gap:.6rem; }
    .dot { width:8px; height:8px; background:var(--accent2); border-radius:50%; display:inline-block; box-shadow:0 0 8px var(--accent2); }
    table { width:100%; border-collapse:collapse; }
    thead th { font-family:'Space Mono',monospace; font-size:.65rem; text-transform:uppercase; letter-spacing:.1em; color:var(--muted); padding:.8rem 1rem; text-align:left; border-bottom:1px solid var(--border); background:var(--surface2); }
    tbody tr { border-bottom:1px solid var(--border); transition:background .15s; }
    tbody tr:last-child { border-bottom:none; }
    tbody tr:hover { background:var(--surface2); }
    tbody td { padding:.85rem 1rem; font-size:.85rem; font-family:'Space Mono',monospace; }
    .empty { padding:2rem; text-align:center; color:var(--muted); font-family:'Space Mono',monospace; font-size:.8rem; }
    a.detail-link { color:var(--accent); text-decoration:none; } a.detail-link:hover { text-decoration:underline; }
    footer { margin-top:3rem; text-align:center; font-family:'Space Mono',monospace; font-size:.65rem; color:var(--muted); }
  </style>
</head>
<body>
<div class="container">
  <header>
    <span class="label">🕓 Historique</span>
    <h1>Exécutions passées</h1>
  </header>
  <a href="/" class="btn">← Retour au dashboard</a>
  <div class="table-wrap">
    <h2><span class="dot"></span> 10 dernières exécutions</h2>
    {% if history %}
    <table>
      <thead><tr><th>#</th><th>Date</th><th>Tests</th><th>Passés</th><th>Échoués</th><th>Succès</th><th>Moy. ms</th><th>Détails</th></tr></thead>
      <tbody>
        {% for h in history %}
        <tr>
          <td style="color:var(--accent2)">{{ h.id }}</td>
          <td>{{ h.executed_at }}</td>
          <td>{{ h.total }}</td>
          <td style="color:var(--green)">{{ h.passed }}</td>
          <td style="color:var(--red)">{{ h.failed }}</td>
          <td style="color:{% if h.success_rate == 100 %}var(--green){% elif h.success_rate >= 75 %}var(--yellow){% else %}var(--red){% endif %}">{{ h.success_rate }}%</td>
          <td style="color:var(--yellow)">{{ h.avg_ms or '—' }}</td>
          <td><a href="/history/{{ h.id }}" class="detail-link">voir →</a></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <div class="empty">Aucune exécution enregistrée. Lance d'abord les tests depuis le dashboard !</div>
    {% endif %}
  </div>
  <footer>API MONITOR &nbsp;·&nbsp; OPEN-METEO &nbsp;·&nbsp; SQLITE &nbsp;·&nbsp; PYTHONANYWHERE</footer>
</div>
</body>
</html>
"""

DETAIL_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8"/>
  <title>Détail exécution #{{ execution.id }}</title>
  <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet"/>
  <style>
    :root { --bg:#0b0f1a; --surface:#111827; --surface2:#1a2236; --accent:#38bdf8; --accent2:#818cf8; --green:#34d399; --red:#f87171; --yellow:#fbbf24; --text:#e2e8f0; --muted:#64748b; --border:#1e2d42; }
    * { box-sizing:border-box; margin:0; padding:0; }
    body { background:var(--bg); color:var(--text); font-family:'Syne',sans-serif; min-height:100vh; padding:2rem 1.5rem 4rem; }
    .container { max-width:1000px; margin:0 auto; }
    header { border-left:4px solid var(--accent2); padding-left:1.2rem; margin-bottom:2.5rem; }
    header .label { font-family:'Space Mono',monospace; font-size:.7rem; color:var(--accent2); letter-spacing:.2em; text-transform:uppercase; }
    header h1 { font-size:2rem; font-weight:800; color:var(--text); }
    header .meta { font-family:'Space Mono',monospace; font-size:.72rem; color:var(--muted); margin-top:.3rem; }
    .btn { display:inline-flex; align-items:center; padding:.6rem 1.4rem; border-radius:8px; font-family:'Space Mono',monospace; font-size:.75rem; font-weight:700; text-decoration:none; background:var(--surface2); color:var(--text); border:1px solid var(--border); margin-bottom:2rem; transition:border-color .2s; }
    .btn:hover { border-color:var(--accent); }
    .table-wrap { background:var(--surface); border:1px solid var(--border); border-radius:12px; overflow:hidden; }
    .table-wrap h2 { font-size:1rem; font-weight:700; padding:1.2rem 1.5rem; border-bottom:1px solid var(--border); }
    table { width:100%; border-collapse:collapse; }
    thead th { font-family:'Space Mono',monospace; font-size:.65rem; text-transform:uppercase; letter-spacing:.1em; color:var(--muted); padding:.8rem 1rem; text-align:left; border-bottom:1px solid var(--border); background:var(--surface2); }
    tbody tr { border-bottom:1px solid var(--border); transition:background .15s; }
    tbody tr:last-child { border-bottom:none; }
    tbody tr:hover { background:var(--surface2); }
    tbody td { padding:.85rem 1rem; font-size:.85rem; }
    .badge { display:inline-flex; align-items:center; gap:.35rem; padding:.25rem .75rem; border-radius:999px; font-family:'Space Mono',monospace; font-size:.7rem; font-weight:700; }
    .badge-pass { background:rgba(52,211,153,.12); color:var(--green); border:1px solid rgba(52,211,153,.3); }
    .badge-fail { background:rgba(248,113,113,.12); color:var(--red); border:1px solid rgba(248,113,113,.3); }
    .badge::before { content:''; width:6px; height:6px; border-radius:50%; background:currentColor; }
    footer { margin-top:3rem; text-align:center; font-family:'Space Mono',monospace; font-size:.65rem; color:var(--muted); }
  </style>
</head>
<body>
<div class="container">
  <header>
    <span class="label">📋 Détail</span>
    <h1>Exécution #{{ execution.id }}</h1>
    <span class="meta">{{ execution.executed_at }} &nbsp;·&nbsp; {{ execution.passed }}/{{ execution.total }} PASS &nbsp;·&nbsp; {{ execution.success_rate }}% succès</span>
  </header>
  <a href="/history" class="btn">← Retour à l'historique</a>
  <div class="table-wrap">
    <h2>Résultats détaillés</h2>
    <table>
      <thead><tr><th>ID</th><th>Nom du test</th><th>HTTP</th><th>Temps (ms)</th><th>Statut</th><th>Erreur</th></tr></thead>
      <tbody>
        {% for r in results %}
        <tr>
          <td style="font-family:'Space Mono',monospace;color:var(--accent2)">{{ r.test_id }}</td>
          <td><strong>{{ r.test_name }}</strong></td>
          <td style="font-family:'Space Mono',monospace;color:{% if r.http_code == 200 %}var(--green){% elif r.http_code and r.http_code < 400 %}var(--yellow){% else %}var(--red){% endif %}">{{ r.http_code or '—' }}</td>
          <td style="font-family:'Space Mono',monospace;color:var(--yellow)">{{ r.response_ms or '—' }}</td>
          <td><span class="badge badge-{{ r.status|lower }}">{{ r.status }}</span></td>
          <td style="font-family:'Space Mono',monospace;font-size:.7rem;color:var(--red)">{{ r.error or '' }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  <footer>API MONITOR &nbsp;·&nbsp; OPEN-METEO &nbsp;·&nbsp; SQLITE &nbsp;·&nbsp; PYTHONANYWHERE</footer>
</div>
</body>
</html>
"""


@app.route("/")
def index():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id FROM executions ORDER BY executed_at DESC LIMIT 1")
        last = cur.fetchone()
        conn.close()
        if last:
            execution, res = get_execution_details(last["id"])
            qos = {
                "total": execution["total"], "passed": execution["passed"],
                "failed": execution["failed"], "success_rate": execution["success_rate"],
                "avg_response_ms": execution["avg_ms"] or "N/A",
                "min_response_ms": execution["min_ms"] or "N/A",
                "max_response_ms": execution["max_ms"] or "N/A",
                "timestamp": execution["executed_at"],
            }
            adapted = [{"id": r["test_id"], "name": r["test_name"],
                        "description": "—", "expected": "—",
                        "status": r["status"], "http_code": r["http_code"],
                        "response_time_ms": r["response_ms"], "error": r["error"]} for r in res]
            return render_template_string(HTML_TEMPLATE, results=adapted, qos=qos)
    except Exception:
        pass
    results, qos = run_and_save_tests()
    return render_template_string(HTML_TEMPLATE, results=results, qos=qos)


@app.route("/run")
def run():
    run_and_save_tests()
    return redirect(url_for("index"))


@app.route("/history")
def history():
    rows = get_history()
    return render_template_string(HISTORY_TEMPLATE, history=rows)


@app.route("/history/<int:exec_id>")
def history_detail(exec_id):
    execution, results = get_execution_details(exec_id)
    if not execution:
        return redirect(url_for("history"))
    return render_template_string(DETAIL_TEMPLATE, execution=execution, results=results)



if __name__ == "__main__":
    init_db()
    print(f"[DB] SQLite initialisée → {DB_PATH}")
    app.run(debug=True)