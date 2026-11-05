# Importing the yfinance package
import sys
from datetime import date

import yfinance as yf

#
# Este metodo retorna un pandas dataframe con datos economicos relacionados
# con un 'stock' (e.g. GOOGL, AMZN) entre una fecha inicial (sd) y una fecha
# final (ed). Las fechas pueden estar en formato 'YYYY-MM-DD'.
#
# sd: fecha inicial
# stock: nombre codigo de la accion
# ed: fecha final. En caso que el usuario no lo indique, se toma la fecha
#     del dia de hoy (se calcula en cada llamada, no al importar el modulo)
#


def get_stock_data(sd, stock, ed=None):
    if ed is None:
        ed = date.today().isoformat()
    data = yf.download(stock, start=sd, end=ed, progress=False, auto_adjust=False)
    # Las versiones recientes de yfinance devuelven columnas MultiIndex
    # (Precio, Ticker); se aplanan para que la tabla se vea limpia.
    if hasattr(data.columns, "nlevels") and data.columns.nlevels > 1:
        data.columns = data.columns.get_level_values(0)
    return data


def test(ticker="GOOGL"):
    start_date = "2020-01-01"
    return get_stock_data(start_date, ticker)


if __name__ == "__main__":
    ticker = "GOOGL"
    if len(sys.argv) == 2:
        ticker = sys.argv[1]
    print(f"Se recuperara informacion del stock ${ticker}")
    data = test(ticker)
    print(data.tail())
