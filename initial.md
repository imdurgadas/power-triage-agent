Project Name:IBM Power Porting Triage Agent

Problem Statement:

Customer & Persona:IBM Infrastructure sales and technical pre-sales teams qualifying customer application migration to IBM Power (ppc64le).

Business Problem:Assessing porting readiness is a tedious, manual process due to unstandardized application dependency lists and fragmented availability sources across distro repos, container registries, and GitHub ecosystem trackers.

Estimation Gap:When components lack ready-to-use Power binaries, teams have no fast, standardized heuristic to roughly gauge porting complexity and initial person-day effort.

Business Impact:High pre-sales turnaround times create deal friction, consume porting team bandwidth on preliminary triage, and risk misjudging migration scope.

Proposed Opportunity:Build a lightweight, agentic AI prototype that parses dependency inputs, orchestrates multi-source availability lookups, applies baseline complexity heuristics (e.g., codebase size, language, arch-specific indicators) to estimate porting effort ranges, and generates an initial feasibility assessment summary for sales qualification.

