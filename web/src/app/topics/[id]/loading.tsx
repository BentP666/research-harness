import { Skeleton } from "@/components/ui/skeleton";

export default function TopicLoading() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <Skeleton className="h-6 w-32" />
      <Skeleton className="h-10 w-3/4" />
      <Skeleton className="h-5 w-1/2" />
      <Skeleton className="h-32 w-full rounded-2xl" />
      <Skeleton className="h-72 w-full rounded-2xl" />
      <Skeleton className="h-48 w-full rounded-2xl" />
    </div>
  );
}
