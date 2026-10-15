import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    version: "5.0.0",
    mode: "blocks",
    dev_mode: false,
    components: [],
    dependencies: [],
  });
}
