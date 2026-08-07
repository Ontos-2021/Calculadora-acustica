from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from .utils.calculations import calculate_resonance_modes, calculate_rt60
from .utils.evaluations import criterio_de_bonello
from .utils.helpers import create_plot, create_rt60_plot

main = Blueprint('main', __name__)

MATERIALS = {
    'Concreto': {'alpha': 0.05, 'label': 'Concreto / Ladrillo visto'},
    'Madera': {'alpha': 0.12, 'label': 'Madera / Parquet'},
    'Yeso': {'alpha': 0.10, 'label': 'Yeso / Drywall'},
    'Vidrio': {'alpha': 0.08, 'label': 'Vidrio'},
    'Alfombra': {'alpha': 0.40, 'label': 'Alfombra gruesa'},
    'Cortina': {'alpha': 0.55, 'label': 'Cortina pesada'},
    'Acustico': {'alpha': 0.70, 'label': 'Panel acústico'},
    'Telgopor': {'alpha': 0.30, 'label': 'Telgopor / Espuma'},
}


@main.route('/')
def index():
    return render_template('index.html', materials=MATERIALS)


@main.route('/results', methods=['POST'])
def results():
    try:
        largo = float(request.form.get('largo'))
        ancho = float(request.form.get('ancho'))
        alto = float(request.form.get('alto'))
        alfas = [float(request.form.get(f'alfa_{i}')) for i in range(1, 7)]

        if largo <= 0 or ancho <= 0 or alto <= 0 or any(alfa < 0 or alfa > 1 for alfa in alfas):
            flash('Las dimensiones deben ser positivas y los coeficientes de absorción deben estar entre 0 y 1.')
            return redirect(url_for('main.index'))

        modos_resonancia = calculate_resonance_modes(largo, ancho, alto)
        rt60_values = calculate_rt60(largo, ancho, alto, alfas)
        bonello_result = criterio_de_bonello(modos_resonancia['frequencies'])

        frequencies = list(bonello_result.keys())
        counts = list(bonello_result.values())
        plot_url = create_plot(frequencies, counts)
        rt60_plot_url = create_rt60_plot(rt60_values)

        return render_template('results.html',
                               modos_resonancia=modos_resonancia,
                               rt60_values=rt60_values,
                               bonello_result=bonello_result,
                               plot_url=plot_url,
                               rt60_plot_url=rt60_plot_url)
    except (ValueError, TypeError):
        flash('Por favor, ingrese valores numéricos válidos.')
        return redirect(url_for('main.index'))


@main.route('/api/calculate', methods=['POST'])
def api_calculate():
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'Se requiere cuerpo JSON'}), 400

    try:
        largo = float(data.get('largo', 0))
        ancho = float(data.get('ancho', 0))
        alto = float(data.get('alto', 0))
        alfas = [float(a) for a in data.get('alfas', [])]

        if len(alfas) != 6:
            return jsonify({'error': 'Se requieren exactamente 6 coeficientes alfa'}), 400
        if largo <= 0 or ancho <= 0 or alto <= 0 or any(a < 0 or a > 1 for a in alfas):
            return jsonify({'error': 'Dimensiones deben ser positivas y alfas entre 0 y 1'}), 400

        modos = calculate_resonance_modes(largo, ancho, alto)
        rt60 = calculate_rt60(largo, ancho, alto, alfas)
        bonello = criterio_de_bonello(modos['frequencies'])

        return jsonify({
            'modos_resonancia': modos,
            'rt60': rt60,
            'bonello': {str(k): v for k, v in bonello.items()},
        })
    except (ValueError, TypeError):
        return jsonify({'error': 'Valores inválidos'}), 400
