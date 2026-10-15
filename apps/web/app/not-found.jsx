import Link from "next/link";
export default function Page() {
  return (
    <div className="state">
      <h1>That page wandered off.</h1>
      <Link href="/" className="button">
        Back to discovery
      </Link>
    </div>
  );
}
