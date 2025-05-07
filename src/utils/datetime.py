import datetime
import pytz

def get_brasilia_datetime():
    """
    Retorna a data e hora atual no fuso horário de Brasília (GMT-3).
    
    Returns:
        str: Data e hora formatada como yyyy-MM-dd Dia da semana as HH:mm
    """
    # Define o fuso horário de Brasília
    brasilia_tz = pytz.timezone('America/Sao_Paulo')
    
    # Obtém a data e hora atual nesse fuso horário
    now = datetime.datetime.now(brasilia_tz)
    
    # Dicionário com os dias da semana em português
    dias_semana = {
        0: "Segunda-feira",
        1: "Terça-feira",
        2: "Quarta-feira",
        3: "Quinta-feira",
        4: "Sexta-feira",
        5: "Sábado",
        6: "Domingo"
    }
    
    # Obtém o dia da semana (0 = Segunda, 6 = Domingo)
    dia_semana = dias_semana[now.weekday()]
    
    # Formata a data e hora como yyyy-MM-dd Dia da semana as HH:mm
    formatted_date = now.strftime("%Y-%m-%d")
    formatted_time = now.strftime("%H:%M")
    formatted_datetime = f"{formatted_date} {dia_semana} as {formatted_time}"
    
    return formatted_datetime
