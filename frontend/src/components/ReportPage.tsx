import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

interface ReportDay {
  date: string;
  signals_count: number;
  movements: number;
  avg_response_ms: number;
  errors: number;
  min_battery_pct: number;
}

interface ReportData {
  username: string;
  date_from: string;
  date_to: string;
  processed_through: string | null;
  days: ReportDay[];
}

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportData | null>(null);

  const downloadReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      await keycloak.updateToken(30);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports`, {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`
        }
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Ошибка ${response.status}`);
      }

      setReport(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!initialized) {
    return <div>Loading...</div>;
  }

  if (!keycloak.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          onClick={() => keycloak.login()}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>
        
        <button
          onClick={downloadReport}
          disabled={loading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Generating Report...' : 'Download Report'}
        </button>

        {report && (
          <table className="mt-4 text-sm border-collapse">
            <caption className="mb-2 text-left text-gray-600">
              {report.username}: данные обработаны по {report.processed_through ?? 'нет данных'}
            </caption>
            <thead>
              <tr>
                <th className="border px-2 py-1">Дата</th>
                <th className="border px-2 py-1">Сигналов</th>
                <th className="border px-2 py-1">Движений</th>
                <th className="border px-2 py-1">Отклик, мс</th>
                <th className="border px-2 py-1">Ошибок</th>
                <th className="border px-2 py-1">Мин. заряд, %</th>
              </tr>
            </thead>
            <tbody>
              {report.days.map((d) => (
                <tr key={d.date}>
                  <td className="border px-2 py-1">{d.date}</td>
                  <td className="border px-2 py-1">{d.signals_count}</td>
                  <td className="border px-2 py-1">{d.movements}</td>
                  <td className="border px-2 py-1">{d.avg_response_ms}</td>
                  <td className="border px-2 py-1">{d.errors}</td>
                  <td className="border px-2 py-1">{d.min_battery_pct}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;