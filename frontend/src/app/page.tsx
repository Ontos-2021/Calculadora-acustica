import { RoomForm } from "@/components/forms/RoomForm";

export default function Home() {
  return (
    <div className="mx-auto max-w-4xl">
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8">
        <h2 className="mb-6 text-xl font-semibold text-gray-800">
          Parámetros de la Sala
        </h2>
        <RoomForm />
      </div>
    </div>
  );
}
