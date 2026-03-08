# tfl new station analysis (big d)

## buckets (initial thoughts)

### 1. transport need
- transit desert mapping using voronoi tessellation of existing stations
- population density overlay (ons census) to find underserved areas
- bus dependency ratio as proxy for latent tube demand
- isochrone mapping to visualise walk-time gaps

### 2. crowding relief
- tfl crowding dataset to find stations/lines over capacity
- model demand redistribution using gravity model
- interchange pressure analysis (bank, kings cross, oxford circus)
- braess's paradox check — does the new station actually help?
- network resilience: what happens when nearby stations close?

### 3. journey time optimisation
- dijkstra's on tube graph to compute current shortest paths
- simulate adding candidate nodes, measure avg journey time delta
- identify worst circuity origin-destination pairs
- cross-london (north-south) connectivity improvements
- first/last mile reduction estimates

### 4. historical tfl station analysis
- how have previous new stations performed?
- what can we learn from past station openings?
- what factors contribute to new station success?

## datasets
- station counts
- ptal grid 2023 (100m x 100m)
- imd 2019 (lsoa level)
- london lsoa boundaries
- tfl station locations + line topology
- census 2021 population (lsoa)
- census 2021 economic activity (lsoa)
- tfl inter-station journey times

## methods
- graph theory (networkx): centrality, shortest paths, connectivity
- spatial analysis (geopandas, shapely): voronoi, isochrones, kde
- demand modelling: gravity/huff models, generalised cost functions
- multi-criteria decision analysis with pareto optimality check
- sensitivity analysis + monte carlo for robustness