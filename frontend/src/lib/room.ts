import type { CalculateRequest, RoomRequest } from "./types";

export function roomPayload(room: CalculateRequest): RoomRequest {
  return {
    largo: room.largo,
    ancho: room.ancho,
    alto: room.alto,
    superficies: room.superficies,
    environment: room.environment,
  };
}
