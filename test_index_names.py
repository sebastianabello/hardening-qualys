#!/usr/bin/env python3
"""
Script de prueba para verificar que los nombres de índices se generan correctamente,
consolidando archivos particionados en el mismo índice.
"""

import re
from pathlib import Path

def _get_index_name_from_file(file_name: str) -> tuple[str, bool]:
    """
    Genera el nombre del índice basado en el nombre del archivo.
    IMPORTANTE: Remueve sufijos de partición (-part-XX) para que todos los archivos
    particionados vayan al MISMO índice de Elasticsearch.
    """
    # Obtener el nombre base del archivo sin extensión
    base_name = Path(file_name).stem  # Elimina .xlsx, .csv, .gz
    
    # Si termina en .csv (para archivos .csv.gz), quitarlo también
    if base_name.endswith('.csv'):
        base_name = base_name[:-4]
    
    # REMOVER sufijo de partición (-part-XX, -part-02, etc.)
    base_name = re.sub(r'-part-\d+$', '', base_name, flags=re.IGNORECASE)
    
    # Convertir a índice válido
    index_name = base_name.lower()
    index_name = re.sub(r'[^a-z0-9\-]', '_', index_name)
    index_name = re.sub(r'_+', '_', index_name)
    index_name = index_name.strip('_')
    
    # Detectar si es ajustada
    ajustada = "ajustado" in file_name.lower()
    
    return index_name, ajustada


def test_index_names():
    """Prueba casos de uso comunes"""
    
    print("🧪 PRUEBAS DE NOMBRES DE ÍNDICES")
    print("=" * 80)
    print()
    
    # Casos de prueba
    test_cases = [
        # Sin particiones
        ("cliente-hardening-2024-octubre-16.csv", "cliente-hardening-2024-octubre-16", False),
        ("cliente-hardening-control-statics-2024-octubre-16.csv", "cliente-hardening-control-statics-2024-octubre-16", False),
        ("cliente-hardening-2024-octubre-16-ajustado.csv", "cliente-hardening-2024-octubre-16-ajustado", True),
        ("cliente-hardening-control-statics-2024-octubre-16-ajustado.csv", "cliente-hardening-control-statics-2024-octubre-16-ajustado", True),
        
        # Con particiones (DEBEN IR AL MISMO ÍNDICE)
        ("cliente-hardening-2024-octubre-16-part-02.csv", "cliente-hardening-2024-octubre-16", False),
        ("cliente-hardening-2024-octubre-16-part-03.csv", "cliente-hardening-2024-octubre-16", False),
        ("cliente-hardening-2024-octubre-16-part-10.csv", "cliente-hardening-2024-octubre-16", False),
        
        ("cliente-hardening-control-statics-2024-octubre-16-part-02.csv", "cliente-hardening-control-statics-2024-octubre-16", False),
        ("cliente-hardening-control-statics-2024-octubre-16-part-05.csv", "cliente-hardening-control-statics-2024-octubre-16", False),
        
        ("cliente-hardening-2024-octubre-16-ajustado-part-02.csv", "cliente-hardening-2024-octubre-16-ajustado", True),
        ("cliente-hardening-2024-octubre-16-ajustado-part-03.csv", "cliente-hardening-2024-octubre-16-ajustado", True),
        
        ("cliente-hardening-control-statics-2024-octubre-16-ajustado-part-02.csv", "cliente-hardening-control-statics-2024-octubre-16-ajustado", True),
        
        # Con compresión gzip
        ("cliente-hardening-2024-octubre-16.csv.gz", "cliente-hardening-2024-octubre-16", False),
        ("cliente-hardening-2024-octubre-16-part-02.csv.gz", "cliente-hardening-2024-octubre-16", False),
        ("cliente-hardening-2024-octubre-16-ajustado-part-03.csv.gz", "cliente-hardening-2024-octubre-16-ajustado", True),
    ]
    
    passed = 0
    failed = 0
    
    for file_name, expected_index, expected_ajustada in test_cases:
        index, ajustada = _get_index_name_from_file(file_name)
        
        if index == expected_index and ajustada == expected_ajustada:
            print(f"✅ PASS: {file_name}")
            print(f"   → {index} (ajustada={ajustada})")
            passed += 1
        else:
            print(f"❌ FAIL: {file_name}")
            print(f"   Esperado: {expected_index} (ajustada={expected_ajustada})")
            print(f"   Obtenido: {index} (ajustada={ajustada})")
            failed += 1
        print()
    
    print("=" * 80)
    print(f"📊 RESULTADOS: {passed} pasaron, {failed} fallaron")
    print()
    
    # Mostrar consolidación
    print("📊 CONSOLIDACIÓN DE ÍNDICES:")
    print("-" * 80)
    
    indices_map = {}
    for file_name, _, _ in test_cases:
        index, _ = _get_index_name_from_file(file_name)
        if index not in indices_map:
            indices_map[index] = []
        indices_map[index].append(file_name)
    
    for index, files in sorted(indices_map.items()):
        print(f"\n📊 Índice: {index}")
        print(f"   Archivos consolidados ({len(files)}):")
        for f in files:
            print(f"   - {f}")
    
    print()
    print(f"✅ Total de índices únicos: {len(indices_map)}")
    print(f"✅ Total de archivos: {len(test_cases)}")
    print(f"✅ Consolidación: {len(test_cases)} archivos → {len(indices_map)} índices")
    
    return failed == 0


if __name__ == "__main__":
    success = test_index_names()
    exit(0 if success else 1)
