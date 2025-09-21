import React from 'react';

const input = {
  width: '100%',
  padding: 12,
  borderRadius: 12,
  border: '1px solid #ddd',
  fontSize: 16,
};
const label = { display: 'block', fontWeight: 600, marginBottom: 6, marginTop: 8 };

export default function StopForm({ originStop, setOriginStop, destStop, setDestStop }) {
  return (
    <div>
      <label style={label}>Origin Stop</label>
      <input
        style={input}
        type="text"
        value={originStop}
        onChange={(e) => setOriginStop(e.target.value)}
        placeholder="e.g., place-babck"
        inputMode="text"
        autoCorrect="off"
        autoCapitalize="none"
      />
      <label style={label}>Destination Stop</label>
      <input
        style={input}
        type="text"
        value={destStop}
        onChange={(e) => setDestStop(e.target.value)}
        placeholder="e.g., 70147"
        inputMode="numeric"
        pattern="[0-9]*"
      />
    </div>
  );
}
