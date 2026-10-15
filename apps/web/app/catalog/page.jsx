import { Suspense } from "react";
import { Catalog } from "../../components/shop";
export default function Page() {
  return (
    <Suspense fallback={<p className="state">Loading…</p>}>
      <Catalog />
    </Suspense>
  );
}
