import { ProductDetail } from "../../../components/shop";
export default async function Page({ params }) {
  const { id } = await params;
  return <ProductDetail id={id} />;
}
