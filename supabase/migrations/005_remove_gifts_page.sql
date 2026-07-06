-- Remove deprecated Gift Planning page thread.
delete from public.conversation_threads where page_type = 'gifts';
