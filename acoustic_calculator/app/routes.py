from flask import Blueprint, render_template, request, flash, redirect, url_for
from .utils.calculations import calculate_resonance_modes, calculate_rt60
from .utils.evaluations import criterio_de_bonello
from .utils.helpers import create_plot

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

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

        return render_template('results.html', modos_resonancia=modos_resonancia, rt60_values=rt60_values,
                               bonello_result=bonello_result, plot_url=plot_url)
    except ValueError:
        flash('Por favor, ingrese valores numéricos válidos.')
        return redirect(url_for('main.index'))
