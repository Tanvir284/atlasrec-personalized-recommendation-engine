import { Suspense } from "react";
import { Profile } from "../../components/shop";
export default function Page() {
  return (
    <Suspense fallback={<p className="state">Loading…</p>}>
      <Profile />
    </Suspense>
  );
}
