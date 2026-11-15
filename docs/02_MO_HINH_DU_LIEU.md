# Mô hình dữ liệu và phân quyền

## Thực thể tối thiểu

| Bảng | Khóa và trường chính |
|---|---|
| users | id,employee_id unique,full_name,active,auth_provider_subject; không lưu mật khẩu thô |
| user_roles | user_id,app_role,scope_workcell_ids; quyền ứng dụng khác chức danh |
| employee_profiles | user_id,job_title,crew,workcell_id,manager_id; lịch sử có effective_at |
| courses/course_versions | id,version,status,digest,published_at,deadline,approved_by; bản published bất biến |
| content_records | version,content_id,kind,public_payload,private_grading_ref,source_refs,asset_refs |
| enrollments | user_id,course_version,required,assigned_roles,status; unique(user_id,course_version) |
| lesson_progress | enrollment_id,lesson_id,card_ids_viewed,check_attempts,completed_at |
| training_sessions | id,type,crew,group,start_at,end_at,timezone,capacity,resources,status |
| session_assignments | session_id,person_id,capacity_role; chặn trùng giờ của người học/người dạy/người chấm |
| attendance | session_id,user_id,status,confirmed_by,confirmed_at,notes |
| assessment_attempts | id,user_id,course_version,type,status,official,policy_snapshot,started_at,expires_at,submitted_at,score,critical_fail_ids,void_reason |
| theory_items/answers | attempt_id,question_snapshot,option_order,response,server_graded_result |
| simulation_events | attempt_id,case_id,seq,event_id unique,idempotency_key,event_type,payload,server_at,previous_state,next_state |
| hardware_observations | attempt_id,criterion_id,pass nullable,notes,evidence_refs,observed_at; unique(attempt_id,criterion_id) |
| assessor_signatures | attempt_id,assessor_id,attestation,server_signed_at; learner_id khác assessor_id |
| role_authorizations | user_id,version,operational_role,warehouse/cell_scope,wcm_review,warehouse_review,system_access_confirmed,valid_from,revoked_at |
| remedial_actions | user_id,failed_attempt_id,lesson_ids,owner,due_at,completed_at,retest_session |
| audit_events | actor,action,target,old_value,new_value,reason,server_at; append-only |

Lưu timestamp UTC, hiển thị Asia/Ho_Chi_Minh; nhận ISO8601 có offset. Điểm và tiến độ gắn với course_version. Lưu snapshot nội dung, đáp án, rubric, chính sách, đề và thứ tự lựa chọn lúc mở đề. Dùng khóa tham chiếu và transaction chống cập nhật nửa chừng. Soft-delete người để giữ lịch sử.

## Ma trận quyền

| Quyền | Người học | Trainer | Assessor | WCM | PM | Content admin | Kho duyệt |
|---|---|---|---|---|---|---|---|
| Xem học/kết quả | Của mình | Lớp được giao | Người được giao | Workcell mình | Toàn Sản xuất | Nội dung | Theo scope |
| Điểm danh | Không | Buổi được giao | Khi được giao | Xem | Xem | Không mặc định | Không mặc định |
| Chấm PDA/ký | Không | Cần thêm quyền Assessor | Người được giao, khác bản thân | Không tự có | Không tự có | Không | Cần quyền Assessor |
| Sửa đáp án/rubric | Không | Không | Không | Đề xuất | Đề xuất | Tạo bản mới | Rà chuyên môn |
| Duyệt vai | Không | Không | Không | Phần WCM, đúng scope | Theo phân công | Không | Xác nhận scope/quyền |
| Xuất dữ liệu người | Của mình | Lớp được giao | Phân công | Workcell mình | Toàn Sản xuất | Không mặc định | Scope được giao |

System admin quản lý kỹ thuật/tài khoản nhưng không mặc định được sửa điểm/chữ ký. Mọi API kiểm actor và scope phía server. Duyệt vai cần xác nhận WCM và Kho phù hợp, không tự duyệt bản thân. Người có nhiều quyền vẫn chịu giới hạn này.

## Import

CSV UTF-8. Employee_id là chuỗi giữ số0đầu. Crew là A/B/C/D hoặc OFFICE khi phù hợp; cần có kíp trước xếp lịch kíp. Operational_roles phân tách bằng dấu `|`. Kiểm ID trùng, tên rỗng, workcell chưa có trong master, vai ngoài danh mục, active/is_placeholder và các trường bắt buộc.

Preview có create/update/reject, hiển thị dòng lỗi; quản trị xác nhận trongapp rồi áp dụng bằng transaction. Upsert theo employee_id, không theo tên. Không xếp placeholder vào thi.

`planned_slots_132.csv` là khung điền người, không phải master nhân sự. Khi có người thật, điền ID,tên,kíp,workcell và đặt is_placeholder=false,active=true. Không tạo mật khẩu trong CSV. Không bắt buộc thu số điện thoại.

Khi xuất CSV, xử lý text nhập từ người dùng bắt đầu bằng `=,+,-,@` để tránh formula injection; số âm thực sự phải giữ kiểu số. Chỉ xuất trong scope. Demo tách database/tenant, không cộng vào báo cáo thật. Sửa quyết định thi qua void có lý do/lượt mới và giữ lịch sử.
