Chronos Reality Tears (pocket-dimension)

What this does
- Reads probe-sequence/spectrum_data/earth_coverage_field.json
- Detects hotspot candidates (heat_sources + hotspot max)
- Produces JSON outputs that describe:
  - hotspot_index.json
  - active_endpoints.json (placeholder geometry payloads)
  - chronos_reality_tears_snapshot.json (bundles config + outputs)

Key files
- chronos_reality_tears_config.json
- reality_tear_hotspot_coord.py

Outputs (configured by chronos_reality_tears_config.json)
- pocket-dimension/hotspot_index.json
- pocket-dimension/active_endpoints.json
- pocket-dimension/chronos_reality_tears_snapshot.json

Hostpoint correlation (IP/DNS + direct client access)
This repo also supports a resolver layer that correlates the hotspot endpoints into “hostpoints” with:
- deterministic ipRange
- generated mirror DNS hostname
- session state (static → active)

Files
- pocket-dimension/hostpoint_resolver.py
  - Input: pocket-dimension/active_endpoints.json (and hotspot_index.json fallback)
  - Output:
    - pocket-dimension/hostpoints_active.json
    - pocket-dimension/hostpoints_session.json

Network service integration
- alive-eal/magi-zone/src/service/network-service.ts
  - GET /hostpoints/active
  - POST /session/activate   { "hostpointId": "hp_<index>" }

Suggested run order
1) python pocket-dimension/reality_tear_hotspot_coord.py
2) python pocket-dimension/hostpoint_resolver.py
3) Start magi-zone network service, then query:
   - http://<host>:<httpPort>/hostpoints/active
   - POST http://<host>:<httpPort>/session/activate

Note on execution environment
- In this repo environment, some Python invocations intermittently fail during Python site initialization.
- If you hit: "Fatal Python error: init_import_site: Failed to import the site module"
  - rerun the script.
  - or run from a fresh terminal.


