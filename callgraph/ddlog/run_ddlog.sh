ddlog -i base.dl &&
(cd base_ddlog && cargo build --release) &&
./base_ddlog/target/release/base_cli < ../base.dat
