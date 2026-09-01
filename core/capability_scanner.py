"""Compatibility facade for the single runtime capability scanner."""
from typing import Any, Dict, List, Optional


class CapabilityScanner:
    def scan_all(self, force: bool = False) -> Dict[str, Any]:
        from backend.services.capability_scanner import get_capability_scanner
        return get_capability_scanner().scan_all(force=force)

    def get_available_ai_services(self) -> List[Dict[str, Any]]:
        return [x for x in self.scan_all()["ai_services"] if x["status"] == "available"]

    def get_best_ai_service(self) -> Optional[Dict[str, Any]]:
        services = self.get_available_ai_services()
        return services[0] if services else None


_scanner: Optional[CapabilityScanner] = None


def get_capability_scanner() -> CapabilityScanner:
    global _scanner
    if _scanner is None:
        _scanner = CapabilityScanner()
    return _scanner
