from flask import Flask, render_template_string
import requests
import time
import datetime
import statistics

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration de l'API Open-Meteo
# ---------------------------------------------------------------------------
API_NAME = "Open-Meteo"
BASE_URL = "https://api.open-meteo.com/v1/forecast"

TESTS_CONFIG = [
    {
        "id": "TC-01",
        "name": "Statut HTTP 200",
        "description": "L'API doit répondre avec un code HTTP 200",
        "params": {
            "latitude": 48.8566,
            "longitude": 2.3522,
            "current_weather": True
        },
        "check": lambda r: r.status_code == 200,
        "expected": "200 OK"
    },
    {
        "id": "TC-02",
        "name": "Présence du champ 'current_weather'",
        "description": "La réponse JSON doit contenir la clé 'current_weather'",
        "params": {
            "latitude": 48.8566,
            "longitude": 2.3522,
            "current_weather": True
        },
        "check": lambda r: "current_weather" in r.json(),
        "expected": "Clé 'current_weather' présente"
    },
    {
        "id": "TC-03",
        "name": "Température dans une plage réaliste",
        "description": "La température doit être comprise entre -60°C et +60°C",
        "params": {
            "latitude": 48.8566,
            "longitude": 2.3522,
            "current_weather": True
        },
        "check": lambda r: -60 <= r.json()["current_weather"]["temperature"] <= 60,
        "expected": "Température entre -60°C et +60°C"
    },
    {
        "id": "TC-04",
        "name": "Coordonnées GPS valides (New York)",
        "description": "L'API doit fonctionner pour des coordonnées différentes",
        "params": {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "current_weather": True
        },
        "check": lambda r: r.status_code == 200 and "current_weather" in r.json(),
        "expected": "200 OK avec current_weather"
    },
    {
        "id": "TC-05",
        "name": "Champ 'windspeed' présent",
        "description": "La vitesse du vent doit être fournie dans current_weather",
        "params": {
            "latitude": 48.8566,
            "longitude": 2.3522,
            "current_weather": True
        },
        "check": lambda r: "windspeed" in r.json().get("current_weather", {}),
        "expected": "Clé 'windspeed' présente"
    },
    {
        "id": "TC-06",
        "name": "Temps de réponse < 3s",
        "description": "L'API doit répondre en moins de 3 secondes",
        "params": {
            "latitude": 48.8566,
            "longitude": 2.3522,
            "current_weather": True
        },
        "check": lambda r: r.elapsed.total_seconds() < 3,
        "expected": "Temps de réponse < 3000 ms"
    },
    {
        "id": "TC-07",
        "name": "Prévisions horaires disponibles",
        "description": "L'API doit retourner des données horaires si demandées",
        "params": {
            "latitude": 48.8566,
            "longitude": 2.3522,
            "hourly": "temperature_2m"
        },
        "check": lambda r: "hourly" in r.json() and "temperature_2m" in r.json()["hourly"],
        "expected": "Données horaires 'temperature_2m' présentes"
    },
    {
        "id": "TC-08",
        "name": "Coordonnées invalides → erreur gérée",
        "description": "L'API doit gérer proprement des coordonnées hors limites",
        "params": {
            "latitude": 9999,
            "longitude": 9999,
            "current_weather": True
        },
        "check": lambda r: r.status_code in [400, 422],
        "expected": "Code 400 ou 422 (erreur attendue)"
    },
]


def run_tests():
    results = []
    response_times = []

    for test in TESTS_CONFIG:
        result = {
            "id": test["id"],
            "name": test["name"],
            "description": test["description"],
            "expected": test["expected"],
            "status": "FAIL",
            "response_time_ms": None,
            "http_code": None,
            "error": None,
        }
        try:
            start = time.time()
            resp = requests.get(BASE_URL, params=test["params"], timeout=10)
            elapsed_ms = (time.time() - start) * 1000

            result["response_time_ms"] = round(elapsed_ms, 1)
            result["http_code"] = resp.status_code
            response_times.append(elapsed_ms)

            if test["check"](resp):
                result["status"] = "PASS"
            else:
                result["status"] = "FAIL"

        except requests.exceptions.Timeout:
            result["error"] = "Timeout"
            result["status"] = "FAIL"
        except Exception as e:
            result["error"] = str(e)
            result["status"] = "FAIL"

        results.append(result)

    # --- Métriques QoS ---
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = total - passed
    success_rate = round((passed / total) * 100, 1) if total > 0 else 0

    qos = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "success_rate": success_rate,
        "avg_response_ms": round(statistics.mean(response_times), 1) if response_times else "N/A",
        "min_response_ms": round(min(response_times), 1) if response_times else "N/A",
        "max_response_ms": round(max(response_times), 1) if response_times else "N/A",
        "timestamp": datetime.datetime.now().strftime("%d/%m/%Y à %H:%M:%S"),
    }

    return results, qos


# ---------------------------------------------------------------------------
# Template HTML
# ---------------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>API Monitor — Open-Meteo</title>
  <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet"/>
  <style>
    :root {
      --bg: #0b0f1a;
      --surface: #111827;
      --surface2: #1a2236;
      --accent: #38bdf8;
      --accent2: #818cf8;
      --green: #34d399;
      --red: #f87171;
      --yellow: #fbbf24;
      --text: #e2e8f0;
      --muted: #64748b;
      --border: #1e2d42;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Syne', sans-serif;
      min-height: 100vh;
      padding: 2rem 1.5rem 4rem;
    }

    /* Noise overlay */
    body::before {
      content: '';
      position: fixed;
      inset: 0;
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
      pointer-events: none;
      z-index: 0;
      opacity: 0.4;
    }

    .container {
      max-width: 1100px;
      margin: 0 auto;
      position: relative;
      z-index: 1;
    }

    /* HEADER */
    header {
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
      margin-bottom: 2.5rem;
      border-left: 4px solid var(--accent);
      padding-left: 1.2rem;
    }

    header .label {
      font-family: 'Space Mono', monospace;
      font-size: 0.7rem;
      color: var(--accent);
      letter-spacing: 0.2em;
      text-transform: uppercase;
    }

    header h1 {
      font-size: 2.2rem;
      font-weight: 800;
      line-height: 1.1;
      background: linear-gradient(90deg, #38bdf8, #818cf8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    header .meta {
      font-family: 'Space Mono', monospace;
      font-size: 0.72rem;
      color: var(--muted);
    }

    /* QoS CARDS */
    .qos-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 1rem;
      margin-bottom: 2.5rem;
    }

    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.2rem 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
      transition: transform 0.2s, border-color 0.2s;
    }

    .card:hover {
      transform: translateY(-2px);
      border-color: var(--accent);
    }

    .card .card-label {
      font-family: 'Space Mono', monospace;
      font-size: 0.65rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }

    .card .card-value {
      font-size: 1.9rem;
      font-weight: 800;
      line-height: 1;
    }

    .card .card-unit {
      font-size: 0.75rem;
      color: var(--muted);
      font-family: 'Space Mono', monospace;
    }

    .accent-blue  { color: var(--accent);  }
    .accent-green { color: var(--green);   }
    .accent-red   { color: var(--red);     }
    .accent-indigo { color: var(--accent2); }
    .accent-yellow { color: var(--yellow); }

    /* PROGRESS BAR */
    .progress-wrap {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.2rem 1.5rem;
      margin-bottom: 2.5rem;
    }

    .progress-wrap h2 {
      font-size: 0.85rem;
      font-family: 'Space Mono', monospace;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin-bottom: 0.8rem;
    }

    .progress-bar-bg {
      background: var(--surface2);
      border-radius: 999px;
      height: 12px;
      overflow: hidden;
    }

    .progress-bar-fill {
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--green), var(--accent));
      transition: width 1s ease;
    }

    .progress-labels {
      display: flex;
      justify-content: space-between;
      margin-top: 0.5rem;
      font-family: 'Space Mono', monospace;
      font-size: 0.7rem;
      color: var(--muted);
    }

    /* TABLE */
    .table-wrap {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
    }

    .table-wrap h2 {
      font-size: 1rem;
      font-weight: 700;
      padding: 1.2rem 1.5rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }

    .table-wrap h2 span.dot {
      width: 8px; height: 8px;
      background: var(--accent);
      border-radius: 50%;
      display: inline-block;
      box-shadow: 0 0 8px var(--accent);
    }

    table {
      width: 100%;
      border-collapse: collapse;
    }

    thead th {
      font-family: 'Space Mono', monospace;
      font-size: 0.65rem;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--muted);
      padding: 0.8rem 1rem;
      text-align: left;
      border-bottom: 1px solid var(--border);
      background: var(--surface2);
    }

    tbody tr {
      border-bottom: 1px solid var(--border);
      transition: background 0.15s;
    }

    tbody tr:last-child { border-bottom: none; }
    tbody tr:hover { background: var(--surface2); }

    tbody td {
      padding: 0.85rem 1rem;
      font-size: 0.88rem;
      vertical-align: top;
    }

    td.id-col {
      font-family: 'Space Mono', monospace;
      font-size: 0.72rem;
      color: var(--accent2);
    }

    td.desc-col {
      color: var(--muted);
      font-size: 0.8rem;
      max-width: 220px;
    }

    td.expected-col {
      font-family: 'Space Mono', monospace;
      font-size: 0.7rem;
      color: var(--muted);
    }

    td.time-col {
      font-family: 'Space Mono', monospace;
      font-size: 0.78rem;
      color: var(--yellow);
    }

    td.http-col {
      font-family: 'Space Mono', monospace;
      font-size: 0.78rem;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.25rem 0.75rem;
      border-radius: 999px;
      font-family: 'Space Mono', monospace;
      font-size: 0.7rem;
      font-weight: 700;
      letter-spacing: 0.05em;
    }

    .badge-pass {
      background: rgba(52, 211, 153, 0.12);
      color: var(--green);
      border: 1px solid rgba(52, 211, 153, 0.3);
    }

    .badge-fail {
      background: rgba(248, 113, 113, 0.12);
      color: var(--red);
      border: 1px solid rgba(248, 113, 113, 0.3);
    }

    .badge::before {
      content: '';
      width: 6px; height: 6px;
      border-radius: 50%;
      background: currentColor;
    }

    /* FOOTER */
    footer {
      margin-top: 3rem;
      text-align: center;
      font-family: 'Space Mono', monospace;
      font-size: 0.65rem;
      color: var(--muted);
      letter-spacing: 0.08em;
    }

    @media (max-width: 600px) {
      header h1 { font-size: 1.5rem; }
      td.desc-col { display: none; }
      td.expected-col { display: none; }
    }
  </style>
</head>
<body>
<div class="container">

  <header>
    <span class="label">⚡ API Quality Monitor</span>
    <h1>Open-Meteo<br>Test Suite</h1>
    <span class="meta">Exécuté le {{ qos.timestamp }} &nbsp;·&nbsp; {{ qos.total }} tests</span>
  </header>

  <!-- QoS Metrics -->
  <div class="qos-grid">
    <div class="card">
      <span class="card-label">Taux de succès</span>
      <span class="card-value accent-green">{{ qos.success_rate }}<span style="font-size:1rem">%</span></span>
      <span class="card-unit">QoS globale</span>
    </div>
    <div class="card">
      <span class="card-label">Tests passés</span>
      <span class="card-value accent-green">{{ qos.passed }}</span>
      <span class="card-unit">sur {{ qos.total }} tests</span>
    </div>
    <div class="card">
      <span class="card-label">Tests échoués</span>
      <span class="card-value accent-red">{{ qos.failed }}</span>
      <span class="card-unit">erreurs détectées</span>
    </div>
    <div class="card">
      <span class="card-label">Temps moyen</span>
      <span class="card-value accent-yellow">{{ qos.avg_response_ms }}</span>
      <span class="card-unit">ms</span>
    </div>
    <div class="card">
      <span class="card-label">Temps min</span>
      <span class="card-value accent-blue">{{ qos.min_response_ms }}</span>
      <span class="card-unit">ms</span>
    </div>
    <div class="card">
      <span class="card-label">Temps max</span>
      <span class="card-value accent-indigo">{{ qos.max_response_ms }}</span>
      <span class="card-unit">ms</span>
    </div>
  </div>

  <!-- Progress bar -->
  <div class="progress-wrap">
    <h2>Taux de réussite global</h2>
    <div class="progress-bar-bg">
      <div class="progress-bar-fill" style="width: {{ qos.success_rate }}%"></div>
    </div>
    <div class="progress-labels">
      <span>0%</span>
      <span style="color: var(--green); font-weight: 700;">{{ qos.success_rate }}%</span>
      <span>100%</span>
    </div>
  </div>

  <!-- Results table -->
  <div class="table-wrap">
    <h2><span class="dot"></span> Résultats des tests</h2>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Nom du test</th>
          <th class="desc-col">Description</th>
          <th class="expected-col">Valeur attendue</th>
          <th>HTTP</th>
          <th>Temps</th>
          <th>Statut</th>
        </tr>
      </thead>
      <tbody>
        {% for r in results %}
        <tr>
          <td class="id-col">{{ r.id }}</td>
          <td><strong>{{ r.name }}</strong></td>
          <td class="desc-col">{{ r.description }}</td>
          <td class="expected-col">{{ r.expected }}</td>
          <td class="http-col">
            {% if r.http_code %}
              <span style="color: {% if r.http_code == 200 %}var(--green){% elif r.http_code < 400 %}var(--yellow){% else %}var(--red){% endif %}">
                {{ r.http_code }}
              </span>
            {% else %}—{% endif %}
          </td>
          <td class="time-col">
            {% if r.response_time_ms %}{{ r.response_time_ms }} ms{% else %}—{% endif %}
          </td>
          <td>
            {% if r.status == 'PASS' %}
              <span class="badge badge-pass">PASS</span>
            {% else %}
              <span class="badge badge-fail">FAIL</span>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <footer>
    API MONITOR &nbsp;·&nbsp; OPEN-METEO &nbsp;·&nbsp; TESTING AS CODE &nbsp;·&nbsp; PYTHONANYWHERE
  </footer>

</div>
</body>
</html>
"""


@app.route("/")
def index():
    results, qos = run_tests()
    return render_template_string(HTML_TEMPLATE, results=results, qos=qos)


if __name__ == "__main__":
    app.run(debug=True)
