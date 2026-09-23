import pytest
from app.services.retrieval.vision_engine import vision_engine


def test_detect_numerical_estimation_triggers_warning():
    # Case with numbers and percentages (typical in chart interpretations)
    text_with_stats = (
        "El gráfico de barras muestra un crecimiento del 24.5% en el año 2023, "
        "alcanzando un total aproximado de 1500 unidades vendidas."
    )
    has_num, warning = vision_engine._detect_numerical_estimation(text_with_stats)
    assert has_num is True
    assert warning is not None
    assert "estimaciones aproximadas" in warning

    # Case purely descriptive without numbers
    text_purely_descriptive = (
        "La figura ilustra el diagrama conceptual del pipeline de datos "
        "con flechas conectando los componentes sin cifras específicas."
    )
    has_num_desc, warning_desc = vision_engine._detect_numerical_estimation(text_purely_descriptive)
    assert has_num_desc is False
    assert warning_desc is None
