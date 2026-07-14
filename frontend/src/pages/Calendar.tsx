import { useState, useEffect } from "react";
import { 
  format, 
  startOfMonth, 
  endOfMonth, 
  eachDayOfInterval, 
  isSameDay, 
  addMonths, 
  subMonths, 
  getDay, 
  isToday 
} from "date-fns";
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useApi, Mission } from "@/lib/api";
import { cn } from "@/lib/utils";

interface CalendarItem {
  id?: string;
  _id?: string;
  type: 'mission' | 'draft' | 'email' | 'agent_log';
  date: Date;
  scheduled_date?: string;
  created_at?: string;
  due_date?: string;
  timestamp?: string;
  content?: string;
  objective?: string;
  subject?: string;
  status?: string;
  [key: string]: unknown;
}

export default function Calendar() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [items, setItems] = useState<CalendarItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const api = useApi();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [missionsData, draftsData, emailTimeline] = await Promise.all([
          api.listMissions(),
          api.getPendingDrafts(),
          api.getEmailTimeline()
        ]);

        const normalizedMissions = (missionsData || []).map((m: Mission) => ({
          ...m,
          type: 'mission',
          date: new Date(m.created_at)
        }));

        const normalizedDrafts = (draftsData || []).map((d: any) => ({
          ...d,
          type: 'draft',
          date: d.created_at ? new Date(d.created_at) : new Date()
        }));

        const timelineEvents = (emailTimeline || []).map((event: any) => ({
          ...event,
          type: 'email',
          date: new Date(event.timestamp)
        }));

        setItems([...normalizedMissions, ...normalizedDrafts, ...timelineEvents]);
      } catch (error) {
        console.error("Failed to fetch calendar data:", error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [api]);

  const nextMonth = () => setCurrentDate(addMonths(currentDate, 1));
  const prevMonth = () => setCurrentDate(subMonths(currentDate, 1));
  const handleToday = () => setCurrentDate(new Date());

  const monthStart = startOfMonth(currentDate);
  const monthEnd = endOfMonth(currentDate);
  const daysInMonth = eachDayOfInterval({ start: monthStart, end: monthEnd });
  const startDay = getDay(monthStart);
  
  // Pad the beginning of the calendar grid
  const paddingDays = Array.from({ length: startDay });
  
  // Pad the end of the calendar grid to ensure full rows
  const totalCells = paddingDays.length + daysInMonth.length;
  const remainingCells = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
  const endPaddingDays = Array.from({ length: remainingCells });

  const getItemsForDay = (date: Date) => {
    return items.filter(item => isSameDay(item.date, date));
  };

  const getEventStyles = (type: string) => {
    switch (type) {
      case 'mission':
        return "bg-indigo-500/20 text-indigo-400 border-indigo-500/30";
      case 'draft':
        return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
      case 'email':
      default:
        return "bg-purple-500/20 text-purple-400 border-purple-500/30";
    }
  };

  const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  return (
    <div className="mx-auto w-full max-w-[1600px] h-full flex flex-col p-4 md:p-6 lg:p-8 space-y-6">
      
      {/* Header Controls */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <CalendarIcon className="w-6 h-6 text-primary" />
            Mission Calendar
          </h1>
          <p className="text-muted-foreground mt-1">Schedule and review agent deployments and drafts.</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center bg-secondary/30 rounded-lg p-1 border border-border">
            <Button variant="ghost" size="icon" onClick={prevMonth} className="h-8 w-8 hover:bg-white/5">
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <span className="w-32 text-center font-medium">
              {format(currentDate, "MMMM yyyy")}
            </span>
            <Button variant="ghost" size="icon" onClick={nextMonth} className="h-8 w-8 hover:bg-white/5">
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
          <Button variant="outline" onClick={handleToday} className="h-10 px-4 font-medium border-border hover:bg-white/5">
            Today
          </Button>
        </div>
      </div>

      {/* Calendar Grid Container */}
      <div className="flex-1 glass-strong rounded-xl overflow-hidden flex flex-col min-h-0 border-border/50">
        
        {/* Days Header */}
        <div className="grid grid-cols-7 border-b border-border/50 bg-secondary/10">
          {WEEKDAYS.map(day => (
            <div key={day} className="p-3 text-sm font-semibold text-muted-foreground text-center">
              {day}
            </div>
          ))}
        </div>

        {/* Days Grid */}
        <div className="flex-1 grid grid-cols-7 auto-rows-fr bg-secondary/5">
          {paddingDays.map((_, i) => (
            <div key={`padding-${i}`} className="border-r border-b border-border/50 bg-background/30 p-2 opacity-30" />
          ))}

          {daysInMonth.map(date => {
            const dayItems = getItemsForDay(date);
            const today = isToday(date);
            
            return (
              <div 
                key={date.toISOString()} 
                className={cn(
                  "border-r border-b border-border/50 p-2 min-h-[120px] transition-colors hover:bg-white/[0.02]",
                  today && "bg-primary/5"
                )}
              >
                <div className="flex justify-between items-start mb-2">
                  <span className={cn(
                    "text-sm font-medium w-7 h-7 flex items-center justify-center rounded-full",
                    today ? "bg-primary text-primary-foreground" : "text-muted-foreground"
                  )}>
                    {format(date, "d")}
                  </span>
                </div>
                
                <div className="space-y-1.5 overflow-y-auto max-h-[140px] terminal-scroll pr-1">
                  {dayItems.map((item, idx) => (
                    <div 
                      key={`${item.id || item._id || idx}`}
                      className={cn(
                        "text-xs px-2 py-1 rounded-md border backdrop-blur-sm truncate shadow-sm",
                        getEventStyles(item.type)
                      )}
                      title={item.objective || item.subject || item.content || item.type}
                    >
                      {item.objective || item.subject || item.content || item.type}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
          
          {endPaddingDays.map((_, i) => (
            <div key={`end-padding-${i}`} className="border-r border-b border-border/50 bg-background/30 p-2 opacity-30" />
          ))}
        </div>
      </div>

    </div>
  );
}
