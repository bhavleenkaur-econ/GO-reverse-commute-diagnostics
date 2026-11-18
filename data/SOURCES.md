# Sources

I assembled these files on 16 November 2026. Raw files are not in git, because several are large. `scripts/download_data.py` fetches them again. With `--seed ../go-station-scorecard/data/raw` it copies the files the GO station scorecard already holds, so the GTFS feeds and the 2021 tables are not downloaded twice.

| Input | What I use it for | Source | Licence |
| --- | --- | --- | --- |
| GO-GTFS.zip | Rail stations, Wednesday 18 Nov 2026 service, and the Saturday and Sunday spans | Metrolinx Open Data, GO Transit GTFS | Open Government Licence – Ontario – Metrolinx |
| UP-GTFS.zip | UP Express stations and service on the same dates | Metrolinx Open Data, UP Express GTFS | Open Government Licence – Ontario – Metrolinx |
| Local GTFS, 14 agencies | Bus stops within 250 m of a destination station, AM bus routes, and the scheduled train-to-bus wait | Mobility Database `latest.zip` for each feed id in `src/reverse/download.py` | Each agency's own open-data licence, named in the feed |
| Table 98-10-0459 | 2021 commuting flows between census subdivisions, usual place of work | Statistics Canada | Open Government Licence – Canada |
| Table 98-10-0498 | 2021 jobs by census tract of work | Statistics Canada | Open Government Licence – Canada |
| 98-400-X2016325 | 2016 commuting flows between census subdivisions, usual place of work | Statistics Canada 2016 Census data table, product id 111332 | Open Government Licence – Canada |
| 98-401-X2016055 | 2016 place-of-work status for each census subdivision: worked at home, usual place of work, no fixed workplace | Statistics Canada 2016 Census Profile, census subdivision file | Open Government Licence – Canada |
| Census Profile characteristics at dissemination area | 2021 place-of-work status, summed to census subdivisions | Statistics Canada 2021 Census Profile, via the Data for Canada Parquet republication of 98-401-X2021 | Open Government Licence – Canada. The Parquet copy holds unmodified values and is not an official Statistics Canada product |
| Tract and subdivision boundaries | Station rings, subdivision coverage, and the flow map | Statistics Canada 2021 cartographic boundary files, same Parquet republication, study-area rows only | Open Government Licence – Canada |

The 2016 files are served from www12.statcan.gc.ca, which answers scripted requests with a browser security check. When that happens, the download script prints the URL and the file name to save. I downloaded both files through a browser and saved them under `data/raw/census` with the names in the table.

I do not use station-level GO ridership or PRESTO. Those series are not on the open-data page, and this project does not estimate boardings.
