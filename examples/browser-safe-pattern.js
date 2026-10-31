// Browser frontend calls YOUR backend, not NexDB with its master key.
async function saveProfile(profile) {
  const response = await fetch("/api/profile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(profile)
  });
  if (!response.ok) throw new Error("Could not save profile");
  return response.json();
}
