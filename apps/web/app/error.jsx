"use client";
export default function Error({ reset }) {
  return (
    <div className="state">
      <h2>Something went wrong.</h2>
      <button className="button" onClick={reset}>
        Try again
      </button>
    </div>
  );
}
