# API Choice

- Étudiant : Florian Huguet
- API choisie : Open-Meteo
- URL base : https://api.open-meteo.com/v1/forecast
- Documentation officielle / README : https://open-meteo.com/en/docs
- Auth : None
- Endpoints testés :
  - GET /v1/forecast?latitude=48.8566&longitude=2.3522&current_weather=true
  - GET /v1/forecast?latitude=48.8566&longitude=2.3522&hourly=temperature_2m
  - GET /v1/forecast?latitude=9999&longitude=9999&current_weather=true
- Hypothèses de contrat (champs attendus, types, codes) :
  - HTTP 200 sur requête valide
  - Réponse JSON avec clé current_weather contenant temperature (float) et windspeed (float)
  - HTTP 400 ou 422 sur coordonnées invalides
- Limites / rate limiting connu : Pas de rate limiting documenté sur le plan gratuit, usage raisonnable attendu
- Risques (instabilité, downtime, CORS, etc.) : API gratuite sans SLA, possibilité de downtime ponctuel, temps de réponse variable selon la charge
