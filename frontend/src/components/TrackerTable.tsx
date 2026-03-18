import './TrackerTable.css';

interface TrackerTableProps {
  satellites: any[];
}

const TrackerTable = ({ satellites = [] }: TrackerTableProps) => {
  return (
    <div className="tracker-table-container glass-panel h-full w-full">
      <table className="tracker-table">
        <thead>
          <tr>
            <th>Satellite</th>
            <th>Azimuth</th>
            <th>Elevation</th>
            <th>Altitude</th>
            <th>Next Event</th>
            <th>Health</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {satellites.map((sat, i) => (
            <tr key={i}>
              <td className="sat-name">{sat.name}</td>
              <td className="mono-text">{(Math.random() * 360).toFixed(2)}°</td>
              <td className="mono-text">{(Math.random() * 90).toFixed(2)}°</td>
              <td className="mono-text">{sat.telemetry.altitude.toFixed(0)} km</td>
              <td className="mono-text">AOS: 2026/03/18 16:00</td>
              <td>{(sat.health * 100).toFixed(0)}%</td>
              <td>
                <span className={`status-badge ${sat.status}`}>{sat.status.toUpperCase()}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default TrackerTable;
