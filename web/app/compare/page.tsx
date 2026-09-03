import { ComparePicker } from "@/components/ComparePicker";
import { loadBoard } from "@/lib/data";

export default function ComparePage() {
  const board = loadBoard();
  return <ComparePicker opportunities={board?.opportunities || []} />;
}
