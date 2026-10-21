import { createClient } from "npm:@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function respond(status: number, body: Record<string, unknown>): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function matchesCode(expected: string, supplied: string): boolean {
  const expectedBytes = new TextEncoder().encode(expected);
  const suppliedBytes = new TextEncoder().encode(supplied);
  if (expectedBytes.length !== suppliedBytes.length) return false;

  let difference = 0;
  for (let index = 0; index < expectedBytes.length; index += 1) {
    difference |= expectedBytes[index] ^ suppliedBytes[index];
  }
  return difference === 0;
}

Deno.serve(async (request: Request) => {
  if (request.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  if (request.method !== "POST") {
    return respond(405, { error: "Método no permitido." });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRoleKey) {
    console.error("Falta la configuración de Supabase para recuperación.");
    return respond(500, { error: "La recuperación no está configurada en el servidor." });
  }

  let body: {
    action?: string;
    email?: string;
    code?: string;
    password?: string;
  };
  try {
    body = await request.json();
  } catch {
    return respond(400, { error: "Solicitud inválida." });
  }

  const email = String(body.email ?? "").trim();
  const code = String(body.code ?? "").trim();
  if (!email || !code) {
    return respond(400, { error: "Escribe el correo y el código." });
  }

  const admin = createClient(supabaseUrl, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  try {
    const { data: profile, error: profileError } = await admin
      .from("usuarios")
      .select("correo, auth_user_id, codigo_sesion")
      .eq("correo", email)
      .maybeSingle();

    if (profileError) {
      console.error("No se pudo consultar el perfil de recuperación:", profileError.message);
      return respond(500, { error: "No se pudo verificar la cuenta." });
    }

    const emailMatches =
      profile?.correo?.toLowerCase() === email.toLowerCase();
    const codeMatches =
      typeof profile?.codigo_sesion === "string" &&
      matchesCode(profile.codigo_sesion, code);
    if (!emailMatches || !codeMatches || !profile?.auth_user_id) {
      return respond(200, { valid: false, ok: false });
    }

    if (body.action === "verify_session_code") {
      return respond(200, { valid: true });
    }
    if (body.action !== "reset_password_with_session_code") {
      return respond(400, { error: "Acción de recuperación no válida." });
    }

    const password = String(body.password ?? "");
    if (password.length < 6) {
      return respond(400, { error: "La contraseña debe tener al menos 6 caracteres." });
    }

    const { error: updateError } = await admin.auth.admin.updateUserById(
      profile.auth_user_id,
      { password },
    );
    if (updateError) {
      console.error("No se pudo actualizar la contraseña de Auth:", updateError.message);
      return respond(400, { error: "Supabase no pudo actualizar la contraseña." });
    }

    return respond(200, { ok: true });
  } catch (error) {
    console.error("Error inesperado en recuperación:", error);
    return respond(500, { error: "Ocurrió un error al recuperar la cuenta." });
  }
});
