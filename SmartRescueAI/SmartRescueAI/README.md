# SmartRescue AI
AI-Powered Smart City Emergency Response Platform (simulation).
Python + Flask + SQLite + Leaflet + Chart.js. Algorithms: BFS, DFS, UCS, A*.

## Folder structure
```
SmartRescueAI/
├── app.py                  # Flask routes  -> THE ONLY FILE YOU RUN
├── requirements.txt
├── README.md
├── core/
│   ├── __init__.py         # empty, keep it
│   ├── search_engine.py    # Graph + BFS, DFS, UCS, A*   (THE AI PART)
│   ├── city_data.py        # nodes, roads, ambulances, hospitals (simulated)
│   ├── dispatch.py         # ambulance selection + hospital ranking
│   └── database.py         # SQLite: incidents, fleet, beds, road closures
├── templates/index.html    # website layout (5 pages)
├── static/css/style.css    # professional theme (light + dark)
├── static/js/app.js        # navigation, live refresh, maps, charts, lab
└── tests/                  # test_core.py (AI), test_app.py (website + saved data)
```

## Run
1. VS Code -> File -> Open Folder -> `SmartRescueAI`
2. Terminal: `pip install flask`
3. Run `app.py` (Run button or `python app.py`), then open http://127.0.0.1:5000
Internet is needed for the map, charts and font.

## Tests
`python -m unittest discover tests -v`

## Saved data
Everything is stored in `smartrescue_v2.db` (created automatically): incidents with their full
results, ambulance status/location, hospital beds, and road closures. Close and reopen the app and
it is all still there. Use "Reset" on the Resources page, or delete the .db file, to start fresh.
