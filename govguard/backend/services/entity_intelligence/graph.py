"""
GovGuard v2 — Cross-Entity Financial Intelligence
===================================================
NEW FILE: services/entity_intelligence/graph.py

Builds entity relationship graph to detect:
  - Shell company networks
  - Related-party transactions
  - Cross-grant beneficial owner conflicts
  - Bid rigging / rotation patterns

GAO Alignment:
  - Cat 1 Ex 4  (PPP/EIDL — beneficial ownership graphs)
  - Cat 1 Ex 26 (Procurement Collusion)
  - Cat 5 Ex 11 (Federated Beneficial-Ownership Graph)
  - Cat 5 Ex 13 (Real-Time PEP/Sanctions Screening)
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EntityNode:
    entity_id: str
    entity_type: str        # VENDOR / APPLICANT / OFFICER / SUBRECIPIENT
    ein_hash: str
    name: str
    risk_score: float = 0.0
    sam_status: str = "unknown"
    pep_flag: bool = False
    sanctions_flag: bool = False


@dataclass
class EntityEdge:
    source_id: str
    target_id: str
    relationship: str   # SHARED_EIN / SHARED_ADDRESS / SHARED_BANK / SHARED_OFFICER / SUBAWARD
    confidence: float   # 0.0–1.0
    evidence: dict = field(default_factory=dict)


@dataclass
class EntityGraph:
    nodes: list[EntityNode]
    edges: list[EntityEdge]
    conflict_flags: list[dict]    # Detected conflicts/rings
    risk_summary: dict


class EntityIntelligenceService:
    """
    Builds and queries the entity relationship graph for a tenant.
    In production: backed by a graph database (Neo4j / AWS Neptune).
    For MVP: operates on in-memory vendor + entity_links data from Postgres.
    """

    def build_graph(
        self,
        vendors: list[dict],
        entity_links: list[dict],
    ) -> EntityGraph:
        """Build graph from existing vendors and entity_links tables."""
        nodes = [
            EntityNode(
                entity_id=str(v.get("id")),
                entity_type="VENDOR",
                ein_hash=v.get("ein_hash", ""),
                name=v.get("name", "Unknown"),
                risk_score=float(v.get("risk_score") or 0),
                sam_status=v.get("sam_status", "unknown"),
            )
            for v in vendors
        ]

        edges = [
            EntityEdge(
                source_id=str(l.get("source_vendor_id")),
                target_id=str(l.get("target_vendor_id")),
                relationship=l.get("link_type", "UNKNOWN"),
                confidence=float(l.get("confidence") or 1.0),
                evidence=l.get("evidence", {}),
            )
            for l in entity_links
        ]

        conflicts = self._detect_conflicts(nodes, edges)
        risk_summary = self._compute_risk_summary(nodes, edges, conflicts)

        return EntityGraph(nodes=nodes, edges=edges, conflict_flags=conflicts, risk_summary=risk_summary)

    def find_related_entities(
        self,
        vendor_id: str,
        graph: EntityGraph,
        max_hops: int = 2,
    ) -> list[EntityNode]:
        """BFS traversal to find entities within max_hops of a vendor."""
        visited = {vendor_id}
        frontier = {vendor_id}

        for _ in range(max_hops):
            next_frontier = set()
            for edge in graph.edges:
                if edge.source_id in frontier and edge.target_id not in visited:
                    next_frontier.add(edge.target_id)
                    visited.add(edge.target_id)
                if edge.target_id in frontier and edge.source_id not in visited:
                    next_frontier.add(edge.source_id)
                    visited.add(edge.source_id)
            frontier = next_frontier

        related_ids = visited - {vendor_id}
        return [n for n in graph.nodes if n.entity_id in related_ids]

    def detect_conflict_of_interest(
        self,
        vendor_id: str,
        grant_id: str,
        graph: EntityGraph,
        grant_officers: list[str],  # user IDs of grant officers
    ) -> Optional[dict]:
        """Check if vendor is linked to a grant officer (related-party conflict)."""
        related = self.find_related_entities(vendor_id, graph)
        for node in related:
            if node.entity_id in grant_officers:
                return {
                    "conflict_type": "RELATED_PARTY",
                    "vendor_id": vendor_id,
                    "grant_id": grant_id,
                    "related_entity": node.entity_id,
                    "gao_reference": "GAO Cat1-Ex26 (Procurement Collusion); Cat5-Ex13 (PEP screening)",
                }
        return None

    def score_vendor_network_risk(
        self,
        vendor_id: str,
        graph: EntityGraph,
    ) -> float:
        """
        Compute network risk score for a vendor based on its graph neighbourhood.
        Penalises: excluded neighbours, high-risk neighbours, PEP flags.
        """
        related = self.find_related_entities(vendor_id, graph, max_hops=2)
        score = 0.0
        for node in related:
            if node.sam_status in ("excluded", "suspended"):
                score += 30.0
            if node.pep_flag:
                score += 20.0
            if node.sanctions_flag:
                score += 35.0
            score += node.risk_score * 0.2   # inherit neighbour risk
        return min(100.0, round(score, 2))

    def link_entities(
        self,
        vendor_a: dict,
        vendor_b: dict,
        transactions_a: list[dict],
        transactions_b: list[dict],
    ) -> list[EntityEdge]:
        """Detect potential links between two vendors based on shared signals."""
        edges = []

        # Shared EIN hash
        if vendor_a.get("ein_hash") and vendor_a["ein_hash"] == vendor_b.get("ein_hash"):
            edges.append(EntityEdge(
                source_id=str(vendor_a["id"]),
                target_id=str(vendor_b["id"]),
                relationship="SHARED_EIN",
                confidence=1.0,
                evidence={"ein_hash": vendor_a["ein_hash"]},
            ))

        # Shared address hash
        if vendor_a.get("address_hash") and vendor_a["address_hash"] == vendor_b.get("address_hash"):
            edges.append(EntityEdge(
                source_id=str(vendor_a["id"]),
                target_id=str(vendor_b["id"]),
                relationship="SHARED_ADDRESS",
                confidence=0.85,
                evidence={"address_hash": vendor_a["address_hash"]},
            ))

        # Shared bank reference
        if vendor_a.get("bank_ref_hash") and vendor_a["bank_ref_hash"] == vendor_b.get("bank_ref_hash"):
            edges.append(EntityEdge(
                source_id=str(vendor_a["id"]),
                target_id=str(vendor_b["id"]),
                relationship="SHARED_BANK",
                confidence=0.95,
                evidence={"bank_ref_hash": vendor_a["bank_ref_hash"]},
            ))

        # Shared invoice dates (rotation pattern — bid rigging signal)
        dates_a = {str(t.get("tx_date")) for t in transactions_a}
        dates_b = {str(t.get("tx_date")) for t in transactions_b}
        overlap = dates_a & dates_b
        if len(overlap) >= 3:
            edges.append(EntityEdge(
                source_id=str(vendor_a["id"]),
                target_id=str(vendor_b["id"]),
                relationship="SYNCHRONIZED_BILLING",
                confidence=0.7,
                evidence={"shared_dates": list(overlap)[:5], "overlap_count": len(overlap)},
            ))

        return edges

    def _detect_conflicts(self, nodes, edges) -> list[dict]:
        """Detect problematic graph patterns."""
        conflicts = []

        # Detect excluded nodes with active edges
        excluded = {n.entity_id for n in nodes if n.sam_status in ("excluded", "suspended")}
        for edge in edges:
            if edge.source_id in excluded or edge.target_id in excluded:
                conflicts.append({
                    "conflict_type": "EXCLUDED_ENTITY_LINK",
                    "edge": {"source": edge.source_id, "target": edge.target_id, "type": edge.relationship},
                    "gao_reference": "GAO Cat5-Ex4 (SAM.gov Exclusion Checks)",
                    "severity": "CRITICAL",
                })

        # Detect hub nodes (single vendor linked to many) — shell company signal
        degree = {}
        for edge in edges:
            degree[edge.source_id] = degree.get(edge.source_id, 0) + 1
            degree[edge.target_id] = degree.get(edge.target_id, 0) + 1
        for nid, deg in degree.items():
            if deg >= 5:
                node = next((n for n in nodes if n.entity_id == nid), None)
                conflicts.append({
                    "conflict_type": "NETWORK_HUB",
                    "entity_id": nid,
                    "entity_name": node.name if node else "Unknown",
                    "degree": deg,
                    "gao_reference": "GAO Cat1-Ex4 (PPP/EIDL — shell entity clustering)",
                    "severity": "HIGH",
                })

        return conflicts

    def _compute_risk_summary(self, nodes, edges, conflicts) -> dict:
        return {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "excluded_nodes": sum(1 for n in nodes if n.sam_status in ("excluded", "suspended")),
            "high_risk_nodes": sum(1 for n in nodes if n.risk_score >= 75),
            "conflict_count": len(conflicts),
            "critical_conflicts": sum(1 for c in conflicts if c.get("severity") == "CRITICAL"),
        }
