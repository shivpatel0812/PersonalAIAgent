-- Rename Learning Assistant page to Personal Assistant.
update public.conversation_threads
set page_type = 'personal', title = 'Personal Assistant'
where page_type = 'learning';

insert into public.conversation_threads (page_type, title)
values ('personal', 'Personal Assistant')
on conflict (page_type) do update set title = excluded.title;
