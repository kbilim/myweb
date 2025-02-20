import pandas as pd
import numpy as np
from binance.client import Client
from binance.enums import *
import ta
import time
from datetime import datetime
import jinja2
from tqdm import tqdm


class BinanceRSIScanner:
    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret)
        self.timeframe = Client.KLINE_INTERVAL_5MINUTE

    def get_perpetual_symbols(self):
        print("Perpetual coinler alınıyor...")
        exchange_info = self.client.futures_exchange_info()
        symbols = [symbol['symbol'] for symbol in exchange_info['symbols']
                   if symbol['status'] == 'TRADING' and 'USDT' in symbol['symbol']]
        print(f"Toplam {len(symbols)} adet coin bulundu")
        return symbols

    def calculate_indicators(self, symbol):
        try:
            klines = self.client.futures_klines(symbol=symbol, interval=self.timeframe, limit=100)
            df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                                               'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote',
                                               'ignored'])
            df['close'] = pd.to_numeric(df['close'])
            df['volume'] = pd.to_numeric(df['volume'])

            # RSI hesaplama
            rsi = ta.momentum.RSIIndicator(df['close'], window=14)
            current_rsi = rsi.rsi().iloc[-1]
            previous_rsi = rsi.rsi().iloc[-2]

            # RSI mutlak fark
            rsi_diff = current_rsi - previous_rsi

            # Hacim değişimi yüzdesi
            current_volume = df['volume'].iloc[-1]
            previous_volume = df['volume'].iloc[-2]
            volume_change = ((current_volume - previous_volume) / previous_volume) * 100

            # Fiyat bilgisi
            current_price = float(df['close'].iloc[-1])

            # Sinyal belirleme (mutlak RSI farkına göre)
            signal = 'NEUTRAL'
            if rsi_diff >= 20:
                signal = 'LONG'
            elif rsi_diff <= -20:
                signal = 'SHORT'

            return {
                'symbol': symbol,
                'current_price': current_price,
                'current_rsi': round(current_rsi, 2),
                'previous_rsi': round(previous_rsi, 2),
                'rsi_diff': round(rsi_diff, 2),
                'volume_change': round(volume_change, 2),
                'signal': signal
            }
        except Exception as e:
            print(f"Hata ({symbol}): {str(e)}")
            return None

    def scan_markets(self):
        results = []
        symbols = self.get_perpetual_symbols()

        print("\nRSI ve Hacim hesaplanıyor...")
        for symbol in tqdm(symbols, desc="İşlenen coinler"):
            result = self.calculate_indicators(symbol)
            if result:
                results.append(result)

        # Sinyallere göre sıralama
        results.sort(key=lambda x: (
            0 if x['signal'] != 'NEUTRAL' else 1,  # Önce sinyal verenler
            -abs(x['rsi_diff'])  # Sonra RSI farkı büyüklüğüne göre
        ))

        return results

    def generate_html(self, results):
        template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Binance 5dk RSI ve Hacim Tarayıcı</title>
            <meta charset="UTF-8">
            <meta http-equiv="refresh" content="60">
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; margin-top: 20px; }
                th, td { border: 1px solid #ddd; padding: 12px; text-align: center; }
                th { background-color: #f2f2f2; }
                .long { background-color: #90EE90; font-weight: bold; }
                .short { background-color: #FFB6C6; font-weight: bold; }
                .neutral { background-color: #FFFFFF; }
                .volume-up { color: #008000; }
                .volume-down { color: #FF0000; }
                .signal-count {
                    margin: 20px 0;
                    padding: 10px;
                    background-color: #f8f9fa;
                    border-radius: 5px;
                }
            </style>
        </head>
        <body>
            <h2>Binance 5 Dakikalık RSI ve Hacim Tarayıcı - Son Güncelleme: {{ current_time }}</h2>
            <p>Bir sonraki güncelleme 1 dakika içinde otomatik olarak yapılacak.</p>

            <div class="signal-count">
                <strong>Sinyal Özeti:</strong>
                <ul>
                    <li>LONG Sinyali (RSI +20 üzeri): {{ signals.long }} coin</li>
                    <li>SHORT Sinyali (RSI -20 altı): {{ signals.short }} coin</li>
                    <li>Toplam Taranan: {{ signals.total }} coin</li>
                </ul>
            </div>

            <table>
                <tr>
                    <th>Sembol</th>
                    <th>Fiyat</th>
                    <th>RSI</th>
                    <th>Önceki RSI</th>
                    <th>RSI Fark</th>
                    <th>Hacim Değişimi %</th>
                    <th>Sinyal</th>
                </tr>
                {% for result in results %}
                <tr>
                    <td><strong>{{ result.symbol }}</strong></td>
                    <td>{{ "%.4f"|format(result.current_price) }}</td>
                    <td>{{ result.current_rsi }}</td>
                    <td>{{ result.previous_rsi }}</td>
                    <td>{{ result.rsi_diff }}</td>
                    <td class="{{ 'volume-up' if result.volume_change > 0 else 'volume-down' }}">
                        {{ result.volume_change }}%
                    </td>
                    <td class="{{ result.signal.lower() }}">{{ result.signal }}</td>
                </tr>
                {% endfor %}
            </table>
        </body>
        </html>
        """

        # Sinyal sayılarını hesapla
        signal_counts = {
            'long': len([r for r in results if r['signal'] == 'LONG']),
            'short': len([r for r in results if r['signal'] == 'SHORT']),
            'total': len(results)
        }

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        html = jinja2.Template(template).render(
            results=results,
            current_time=current_time,
            signals=signal_counts
        )

        with open('rsi1.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"\nSonuçlar 'rsi1.html' dosyasına kaydedildi")


def main():
    print("Binance RSI Tarayıcı başlatılıyor...")

    # API anahtarlarınızı buraya girin
    api_key = 'YOUR_API_KEY'
    api_secret = 'YOUR_API_SECRET'

    scanner = BinanceRSIScanner(api_key, api_secret)

    while True:
        try:
            print("\nTarama başlatılıyor...")
            start_time = time.time()

            results = scanner.scan_markets()
            scanner.generate_html(results)

            end_time = time.time()
            duration = round(end_time - start_time, 2)
            print(f"\nTarama tamamlandı! Süre: {duration} saniye")
            print("60 saniye bekleniyor...")
            time.sleep(60)

        except Exception as e:
            print(f"\nHata oluştu: {str(e)}")
            print("5 saniye sonra tekrar denenecek...")
            time.sleep(5)


if __name__ == "__main__":
    main()