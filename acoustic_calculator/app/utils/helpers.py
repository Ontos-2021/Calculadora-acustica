import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64

def create_plot(frequencies, counts):
    plt.figure(figsize=(10, 6))
    plt.bar(frequencies, counts, color='blue')
    plt.xlabel('Frecuencia (Hz)')
    plt.ylabel('Cantidad de Modos')
    plt.title('Distribución de Modos según el Criterio de Bonello')
    plt.grid(True)

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    return plot_url
