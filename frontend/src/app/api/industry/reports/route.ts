// CF-002: legacy upstream access is disabled for every caller and method.
export {
  unavailableFeature as GET, unavailableFeature as POST,
  unavailableFeature as PUT, unavailableFeature as PATCH,
  unavailableFeature as DELETE, unavailableFeature as HEAD,
  unavailableFeature as OPTIONS,
} from "@/lib/disabled-feature";
