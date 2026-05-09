import { Skeleton } from "@/components/ui/skeleton";

export default function LibraryLoading() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <Skeleton className="h-10 w-48" />
      <Skeleton className="h-5 w-24" />
      <div className="flex gap-2">
        <Skeleton className="h-10 flex-1" />
        <Skeleton className="h-10 w-32" />
      </div>
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full rounded-md" />
        ))}
      </div>
    </div>
  );
}
