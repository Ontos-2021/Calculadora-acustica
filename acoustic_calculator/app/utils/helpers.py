import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from typing import List, Dict, Union

Number = Union[int, float]


def create_plot(frequencies: List[Number], counts: List[int]) -> str:
    plt.figure(figsize=(10, 6))
    if frequencies and len(frequencies) > 1:
        bar_width = max(min(frequencies[1] - frequencies[0], 50), 5)
    else:
        bar_width = 10
    plt.bar(frequencies, counts, color='#4a90d9', width=bar_width, edgecolor='white')
    plt.xlabel('Frecuencia (Hz)')
    plt.ylabel('Cantidad de Modos')
    plt.title('Distribución de Modos según el Criterio de Bonello')
    plt.grid(True, alpha=0.3)

    img = io.BytesIO()
    plt.savefig(img, format='png', dpi=100, bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    return plot_url


def create_rt60_plot(rt60_values: Dict[str, float]) -> str:
    plt.figure(figsize=(8, 5))
    metodos = list(rt60_values.keys())
    valores = list(rt60_values.values())
    colores = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12']

    bars = plt.bar(metodos, valores, color=colores, width=0.6, edgecolor='white', linewidth=1.5)

    for bar, val in zip(bars, valores):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                 f'{val} ms', ha='center', va='bottom', fontweight='bold')

    plt.xlabel('Método')
    plt.ylabel('RT60 (ms)')
    plt.title('Tiempo de Reverberación RT60')
    plt.grid(True, axis='y', alpha=0.3)

    img = io.BytesIO()
    plt.savefig(img, format='png', dpi=100, bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    return plot_url
