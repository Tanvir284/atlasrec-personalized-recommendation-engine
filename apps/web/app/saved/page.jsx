import { Suspense } from "react";
import { Saved } from "../../components/shop";
export default function Page() {
  return (
    <Suspense fallback={<p className="state">Loading…</p>}>
      <Saved />
    </Suspense>
  );
}
