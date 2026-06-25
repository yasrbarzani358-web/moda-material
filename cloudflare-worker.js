export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: corsHeaders(),
      });
    }

    if (request.method !== "POST") {
      return new Response("Send POST request with prompt", { status: 200 });
    }

    const auth = request.headers.get("Authorization") || "";
    const expected = `Bearer ${env.API_KEY}`;

    if (auth !== expected) {
      return new Response("Unauthorized", { status: 401 });
    }

    const body = await request.json();
    const prompt = body.prompt || "seamless architectural material texture";

    const image = await env.AI.run(
      "@cf/stabilityai/stable-diffusion-xl-base-1.0",
      {
        prompt,
      }
    );

    return new Response(image, {
      headers: {
        "content-type": "image/png",
        ...corsHeaders(),
      },
    });
  },
};

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
  };
}
