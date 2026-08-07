import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64


def create_plot(frequencies: list, counts: list[int]) -> str:
    plt.figure(figsize=(10, 6))
    if frequencies and len(frequencies) > 1:
        bar_width = max(min(frequencies[1] - frequencies[0], 50), 5)
    else:
        bar_width = 10
    plt.bar(frequencies, counts, color='#4a90d9', width=bar_width, edgecolor='white')
    plt.xlabel('Frecuencia (Hz)')
    plt.ylabel('Cantidad de Modos')
    plt.title('Distribución de Modos — Criterio de Bonello')
    plt.grid(True, alpha=0.3)

    img = io.BytesIO()
    plt.savefig(img, format='png', dpi=100, bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()
    return plot_url


def create_rt60_plot(rt60_bandas: dict) -> str:
    fig, ax = plt.subplots(figsize=(10, 6))

    metodos = ["Sabine", "Eyring", "Millington", "FitzRoy"]
    bandas = sorted(rt60_bandas.keys())
    colores = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12']

    x = list(range(len(bandas)))
    width = 0.2

    for i, metodo in enumerate(metodos):
        valores = [rt60_bandas[b][metodo] for b in bandas]
        ax.bar([xi + i * width for xi in x], valores, width,
               label=metodo, color=colores[i], edgecolor='white')

    ax.set_xlabel('Banda de frecuencia (Hz)')
    ax.set_ylabel('RT60 (s)')
    ax.set_title('Tiempo de Reverberación por Banda de Octava')
    ax.set_xticks([xi + 1.5 * width for xi in x])
    ax.set_xticklabels(bandas)
    ax.legend()
    ax.grid(True, axis='y', alpha=0.3)

    img = io.BytesIO()
    plt.savefig(img, format='png', dpi=100, bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()
    return plot_url


def create_band_comparison_plot(rt60_bandas: dict, objetivo: dict) -> str:
    fig, ax = plt.subplots(figsize=(10, 6))

    bandas = sorted(rt60_bandas.keys())
    actuales = [rt60_bandas[b]["Sabine"] for b in bandas]
    objetivos = [objetivo.get(b, 0) for b in bandas]

    x = list(range(len(bandas)))
    width = 0.35

    ax.bar([xi - width / 2 for xi in x], actuales, width,
           label='Actual (Sabine)', color='#3498db', edgecolor='white')
    ax.bar([xi + width / 2 for xi in x], objetivos, width,
           label='Objetivo', color='#e74c3c', edgecolor='white', alpha=0.7)

    ax.set_xlabel('Banda de frecuencia (Hz)')
    ax.set_ylabel('RT60 (s)')
    ax.set_title('Comparación RT60 Actual vs. Objetivo')
    ax.set_xticks(x)
    ax.set_xticklabels(bandas)
    ax.legend()
    ax.grid(True, axis='y', alpha=0.3)

    img = io.BytesIO()
    plt.savefig(img, format='png', dpi=100, bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()
    return plot_url
