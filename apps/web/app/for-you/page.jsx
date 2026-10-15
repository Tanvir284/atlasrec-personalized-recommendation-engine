import { Suspense } from "react";
import { ForYou } from "../../components/shop";
export default function Page() {
  return (
    <Suspense fallback={<p className="state">Loading…</p>}>
      <ForYou />
    </Suspense>
  );
}
